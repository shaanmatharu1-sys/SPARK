"""
services/polygon_client.py
Handles:
  - Polygon.io REST (quotes, options chain, snapshots, unusual activity)
  - Polygon.io WebSocket (real-time stocks + options feed)
  - Auto-reconnect with exponential backoff
"""
import asyncio
import json
import logging
import time
from typing import Callable
import aiohttp
import websockets
from config import (
    POLYGON_API_KEY,
    POLYGON_WS_STOCKS,
    POLYGON_WS_OPTIONS,
    DEFAULT_WATCHLIST,
)
from cache.redis_client import cache_set, cache_get, hset_quote, publish
from config import TTL_QUOTE, TTL_OPTIONS, TTL_UNUSUAL

logger = logging.getLogger(__name__)

BASE_REST = "https://api.polygon.io"


# ════════════════════════════════════════════════════════════════
# REST CLIENT
# ════════════════════════════════════════════════════════════════

async def _get(session: aiohttp.ClientSession, path: str, params: dict = {}) -> dict | list | None:
    params["apiKey"] = POLYGON_API_KEY
    url = f"{BASE_REST}{path}"
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
            else:
                body = await r.text()
                logger.warning(f"[Polygon REST] {url} -> {r.status}: {body[:200]}")
                return None
    except Exception as e:
        logger.error(f"[Polygon REST] {url} error: {e}")
        return None


async def fetch_snapshot(symbols: list[str]) -> dict:
    """Get real-time snapshots for a list of tickers (REST fallback)."""
    cached = await cache_get("snapshot:batch")
    if cached:
        return cached
    tickers = ",".join(symbols)
    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/v2/snapshot/locale/us/markets/stocks/tickers", {"tickers": tickers})
    if data and "tickers" in data:
        result = {t["ticker"]: t for t in data["tickers"]}
        await cache_set("snapshot:batch", result, TTL_QUOTE)
        return result
    return {}


async def fetch_options_chain(symbol: str, expiration_date: str = None) -> list:
    """Fetch full options chain for a symbol."""
    cache_key = f"options:{symbol}:{expiration_date or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    params = {"underlying_asset": symbol, "limit": 250, "order": "asc", "sort": "strike_price"}
    if expiration_date:
        params["expiration_date"] = expiration_date

    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v3/reference/options/contracts", params)

    contracts = data.get("results", []) if data else []
    await cache_set(cache_key, contracts, TTL_OPTIONS)
    return contracts


async def fetch_options_snapshot(symbol: str) -> list:
    """Fetch options snapshots with Greeks and IV (requires options subscription)."""
    cache_key = f"options_snapshot:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/v3/snapshot/options/{symbol}", {"limit": 250})

    results = data.get("results", []) if data else []
    await cache_set(cache_key, results, TTL_OPTIONS)
    return results


async def fetch_unusual_activity(symbol: str = None) -> list:
    """Fetch unusual options activity."""
    cache_key = f"unusual:{symbol or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    params = {"order": "desc", "limit": 50}
    if symbol:
        params["underlying_asset"] = symbol

    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v3/snapshot/options/unusual_activity", params)

    results = data.get("results", []) if data else []
    await cache_set(cache_key, results, TTL_UNUSUAL)
    return results


async def fetch_agg_bars(symbol: str, multiplier: int = 1, timespan: str = "minute",
                          from_date: str = None, to_date: str = None, limit: int = 390) -> list:
    """Fetch OHLCV bars for charting."""
    import datetime
    today = datetime.date.today().isoformat()
    month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    from_date = from_date or month_ago
    to_date   = to_date   or today

    cache_key = f"bars:{symbol}:{multiplier}{timespan}:{from_date}:{to_date}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            {"adjusted": "true", "sort": "asc", "limit": limit}
        )

    bars = data.get("results", []) if data else []
    await cache_set(cache_key, bars, 60)
    return bars


async def fetch_ticker_details(symbol: str) -> dict:
    cached = await cache_get(f"details:{symbol}")
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/v3/reference/tickers/{symbol}")
    result = data.get("results", {}) if data else {}
    await cache_set(f"details:{symbol}", result, 86400)
    return result


# ════════════════════════════════════════════════════════════════
# WEBSOCKET — STOCKS FEED
# ════════════════════════════════════════════════════════════════

class PolygonStocksWS:
    """
    Maintains a persistent WebSocket connection to Polygon stocks feed.
    On each message, updates Redis and publishes to the 'quotes' pub/sub channel.
    Auto-reconnects with exponential backoff.
    """

    def __init__(self, symbols: list[str] = None):
        self.symbols   = symbols or DEFAULT_WATCHLIST
        self.running   = False
        self._ws       = None

    async def start(self):
        self.running = True
        backoff = 1
        while self.running:
            try:
                await self._connect()
                backoff = 1
            except Exception as e:
                logger.error(f"[Polygon WS Stocks] Disconnected: {e}. Reconnect in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def stop(self):
        self.running = False
        if self._ws:
            await self._ws.close()

    async def _connect(self):
        logger.info(f"[Polygon WS Stocks] Connecting -> {POLYGON_WS_STOCKS}")
        async with websockets.connect(POLYGON_WS_STOCKS, ping_interval=20) as ws:
            self._ws = ws
            async for raw in ws:
                messages = json.loads(raw)
                for msg in messages:
                    ev = msg.get("ev")
                    if ev == "connected":
                        await ws.send(json.dumps({"action": "auth", "params": POLYGON_API_KEY}))
                    elif ev == "auth_success":
                        subs = ",".join([
                            f"T.{s}" for s in self.symbols   # Trades
                        ] + [
                            f"Q.{s}" for s in self.symbols   # Quotes
                        ] + [
                            f"AM.{s}" for s in self.symbols  # Agg minute bars
                        ])
                        await ws.send(json.dumps({"action": "subscribe", "params": subs}))
                        logger.info(f"[Polygon WS Stocks] Subscribed to {len(self.symbols)} symbols")
                    elif ev == "auth_failed":
                        logger.error("[Polygon WS Stocks] Auth failed — check API key")
                        return
                    elif ev in ("T", "Q", "AM", "A"):
                        await self._handle_market_msg(msg)

    async def _handle_market_msg(self, msg: dict):
        ev     = msg.get("ev")
        symbol = msg.get("sym") or msg.get("s", "")

        if ev == "T":   # Trade
            quote = {
                "type":   "trade",
                "symbol": symbol,
                "price":  msg.get("p"),
                "size":   msg.get("s"),
                "ts":     msg.get("t"),
                "cond":   msg.get("c", []),
            }
        elif ev == "Q":  # Quote
            quote = {
                "type":   "quote",
                "symbol": symbol,
                "bid":    msg.get("bp"),
                "ask":    msg.get("ap"),
                "bid_sz": msg.get("bs"),
                "ask_sz": msg.get("as"),
                "ts":     msg.get("t"),
            }
        elif ev in ("AM", "A"):  # Aggregate bar
            quote = {
                "type":   "bar",
                "symbol": symbol,
                "open":   msg.get("o"),
                "high":   msg.get("h"),
                "low":    msg.get("l"),
                "close":  msg.get("c"),
                "volume": msg.get("v"),
                "vwap":   msg.get("vw"),
                "ts":     msg.get("s"),
            }
        else:
            return

        await hset_quote(symbol, quote)
        await publish("quotes", quote)


# ════════════════════════════════════════════════════════════════
# WEBSOCKET — OPTIONS FEED
# ════════════════════════════════════════════════════════════════

class PolygonOptionsWS:
    """
    Connects to Polygon options feed for real-time options quotes.
    """

    def __init__(self, symbols: list[str] = None):
        self.symbols = symbols or DEFAULT_WATCHLIST
        self.running = False

    async def start(self):
        self.running = True
        backoff = 1
        while self.running:
            try:
                await self._connect()
                backoff = 1
            except Exception as e:
                logger.error(f"[Polygon WS Options] Disconnected: {e}. Reconnect in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def stop(self):
        self.running = False

    async def _connect(self):
        logger.info(f"[Polygon WS Options] Connecting -> {POLYGON_WS_OPTIONS}")
        async with websockets.connect(POLYGON_WS_OPTIONS, ping_interval=20) as ws:
            async for raw in ws:
                messages = json.loads(raw)
                for msg in messages:
                    ev = msg.get("ev")
                    if ev == "connected":
                        await ws.send(json.dumps({"action": "auth", "params": POLYGON_API_KEY}))
                    elif ev == "auth_success":
                        subs = ",".join([f"O:{s}" for s in self.symbols])
                        await ws.send(json.dumps({"action": "subscribe", "params": subs}))
                        logger.info("[Polygon WS Options] Subscribed")
                    elif ev == "O":
                        await self._handle_options_msg(msg)

    async def _handle_options_msg(self, msg: dict):
        data = {
            "type":     "options_quote",
            "contract": msg.get("sym"),
            "bid":      msg.get("bp"),
            "ask":      msg.get("ap"),
            "bid_sz":   msg.get("bs"),
            "ask_sz":   msg.get("as"),
            "ts":       msg.get("t"),
        }
        await publish("options", data)


# ════════════════════════════════════════════════════════════════
# MOVERS, CRYPTO, EARNINGS  (REST)
# ════════════════════════════════════════════════════════════════

async def fetch_movers(direction: str = "gainers") -> list:
    """Top gainers or losers for the day. direction: 'gainers' | 'losers'."""
    cache_key = f"movers:{direction}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"/v2/snapshot/locale/us/markets/stocks/{direction}", {})
    movers = []
    for t in (data.get("tickers", []) if data else []):
        movers.append({
            "symbol":     t.get("ticker"),
            "price":      t.get("lastTrade", {}).get("p") or t.get("day", {}).get("c"),
            "change":     t.get("todaysChange"),
            "change_pct": round(t.get("todaysChangePerc", 0), 2),
            "volume":     t.get("day", {}).get("v"),
        })
    await cache_set(cache_key, movers, 30)
    return movers


async def fetch_crypto_snapshot(symbols: list[str] = None) -> dict:
    """Crypto snapshots. symbols like ['X:BTCUSD','X:ETHUSD']."""
    symbols = symbols or ["X:BTCUSD", "X:ETHUSD", "X:SOLUSD", "X:DOGEUSD"]
    cache_key = "crypto:snapshot"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    tickers = ",".join(symbols)
    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            "/v2/snapshot/locale/global/markets/crypto/tickers", {"tickers": tickers})
    result = {}
    for t in (data.get("tickers", []) if data else []):
        sym = t.get("ticker", "")
        day = t.get("day", {})
        prev = t.get("prevDay", {})
        result[sym] = {
            "symbol":     sym.replace("X:", ""),
            "price":      t.get("lastTrade", {}).get("p") or day.get("c"),
            "change_pct": round(t.get("todaysChangePerc", 0), 2),
            "high":       day.get("h"),
            "low":        day.get("l"),
            "volume":     day.get("v"),
            "prev_close": prev.get("c"),
        }
    await cache_set(cache_key, result, 10)
    return result


async def fetch_crypto_bars(symbol: str = "X:BTCUSD", days: int = 30) -> list:
    """OHLCV bars for a crypto symbol."""
    import datetime
    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    cache_key = f"crypto_bars:{symbol}:{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{today}",
            {"adjusted": "true", "sort": "asc", "limit": 5000})
    bars = data.get("results", []) if data else []
    await cache_set(cache_key, bars, 300)
    return bars


async def fetch_earnings(symbol: str) -> dict:
    """
    Earnings data via Polygon. Uses the financials endpoint for actuals.
    Note: estimate/surprise data availability depends on Polygon tier.
    """
    cache_key = f"earnings:{symbol.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/vX/reference/financials",
            {"ticker": symbol.upper(), "limit": 8, "timeframe": "quarterly",
             "order": "desc", "sort": "filing_date"})
    results = []
    for f in (data.get("results", []) if data else []):
        fin = f.get("financials", {})
        inc = fin.get("income_statement", {})
        results.append({
            "fiscal_period": f.get("fiscal_period"),
            "fiscal_year":   f.get("fiscal_year"),
            "filing_date":   f.get("filing_date"),
            "revenue":       inc.get("revenues", {}).get("value"),
            "net_income":    inc.get("net_income_loss", {}).get("value"),
            "eps_basic":     inc.get("basic_earnings_per_share", {}).get("value"),
            "eps_diluted":   inc.get("diluted_earnings_per_share", {}).get("value"),
        })
    out = {"symbol": symbol.upper(), "quarters": results}
    await cache_set(cache_key, out, 3600)
    return out
