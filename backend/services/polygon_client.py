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
    WS_CIRCUIT_BREAKER_THRESHOLD,
    WS_CIRCUIT_BREAKER_COOLDOWN,
    WS_RECV_TIMEOUT,
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
    import hashlib
    key = "snapshot:" + hashlib.md5(",".join(sorted(symbols)).encode()).hexdigest()[:12]
    cached = await cache_get(key)
    if cached:
        return cached
    tickers = ",".join(symbols)
    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/v2/snapshot/locale/us/markets/stocks/tickers", {"tickers": tickers})
    if data and "tickers" in data:
        result = {t["ticker"]: t for t in data["tickers"]}
        await cache_set(key, result, TTL_QUOTE)
        return result
    return {}


async def fetch_fx_snapshot(symbols: list[str]) -> dict:
    """Get FX snapshots (Polygon forex endpoint). Symbols like 'C:EURUSD'."""
    import hashlib
    key = "fxsnap:" + hashlib.md5(",".join(sorted(symbols)).encode()).hexdigest()[:12]
    cached = await cache_get(key)
    if cached:
        return cached
    tickers = ",".join(symbols)
    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v2/snapshot/locale/global/markets/forex/tickers",
                          {"tickers": tickers})
    if data and "tickers" in data:
        result = {t["ticker"]: t for t in data["tickers"]}
        await cache_set(key, result, TTL_QUOTE)
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


async def search_tickers(query: str, limit: int = 15) -> list:
    """
    Search the FULL market for tickers by symbol or company name prefix —
    not just the curated ~500-name S&P universe in data_universe.py. Backs
    the global symbol search so any listed US equity is discoverable.
    """
    query = (query or "").strip()
    if not query:
        return []
    cache_key = f"ticker_search:{query.lower()}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    params = {"search": query, "market": "stocks", "active": "true",
              "order": "asc", "limit": limit, "sort": "ticker"}
    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v3/reference/tickers", params)

    results = []
    for r in (data.get("results", []) if data else []):
        results.append({
            "ticker":          r.get("ticker"),
            "name":            r.get("name"),
            "exchange":        r.get("primary_exchange"),
            "type":            r.get("type"),
            "currency":        r.get("currency_name"),
        })
    await cache_set(cache_key, results, 3600)
    return results


async def fetch_options_snapshot(symbol: str, max_pages: int = 8) -> list:
    """
    Fetch options snapshots with Greeks and IV (requires options subscription).
    A single page (limit=250) only covers the nearest, most strike-dense
    expiration for liquid underlyings — e.g. a vol surface needs contracts
    across MANY expirations to build a term structure, so this follows
    Polygon's next_url cursor across pages (capped) rather than returning
    just the first page.
    """
    cache_key = f"options_snapshot:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = []
    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"/v3/snapshot/options/{symbol}", {"limit": 250})
        if data:
            results.extend(data.get("results", []))
            next_url = data.get("next_url")
            pages = 1
            while next_url and pages < max_pages:
                async with session.get(next_url, params={"apiKey": POLYGON_API_KEY},
                                       timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        break
                    page = await r.json()
                results.extend(page.get("results", []))
                next_url = page.get("next_url")
                pages += 1

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


# Lookback window must be wide enough to actually contain `limit` bars for a given
# timespan, otherwise a narrow default (e.g. 30 days) silently truncates 3M/1Y requests
# to whatever fits in 30 days instead of the range the user asked for.
_LOOKBACK_DAYS = {
    "minute": 10,
    "hour":   60,
    "day":    400,
    "week":   800,
    "month":  1800,
}


async def fetch_agg_bars(symbol: str, multiplier: int = 1, timespan: str = "minute",
                          from_date: str = None, to_date: str = None, limit: int = 390) -> list:
    """Fetch OHLCV bars for charting."""
    import datetime
    today = datetime.date.today().isoformat()
    if from_date is None:
        lookback = _LOOKBACK_DAYS.get(timespan, 400) * max(multiplier, 1)
        from_date = (datetime.date.today() - datetime.timedelta(days=lookback)).isoformat()
    to_date = to_date or today

    cache_key = f"bars:{symbol}:{multiplier}{timespan}:{from_date}:{to_date}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    async with aiohttp.ClientSession() as session:
        data = await _get(session,
            f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            # sort=desc + limit grabs the most recent `limit` bars regardless of how wide
            # the lookback window is; reversed below into chronological order for the chart.
            {"adjusted": "true", "sort": "desc", "limit": limit}
        )

    bars = data.get("results", []) if data else []
    bars.reverse()
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


async def fetch_dividends(symbol: str) -> list:
    """Cash dividend history for a ticker (declaration/ex/record/pay dates + amount)."""
    cache_key = f"dividends:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v3/reference/dividends",
            {"ticker": symbol, "limit": 50, "order": "desc", "sort": "ex_dividend_date"})
    results = data.get("results", []) if data else []
    await cache_set(cache_key, results, 86400)  # 24h — dividend history rarely changes intraday
    return results


async def fetch_splits(symbol: str) -> list:
    """Stock split history for a ticker (execution date + split ratio)."""
    cache_key = f"splits:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    async with aiohttp.ClientSession() as session:
        data = await _get(session, "/v3/reference/splits",
            {"ticker": symbol, "limit": 50, "order": "desc", "sort": "execution_date"})
    results = data.get("results", []) if data else []
    await cache_set(cache_key, results, 86400)  # 24h — splits are rare, infrequent events
    return results


# ════════════════════════════════════════════════════════════════
# WEBSOCKET — shared reliability base
# ════════════════════════════════════════════════════════════════
#
# Root-cause note (found by live diagnostic testing, not inference): Polygon's
# "connected"/"auth_success"/"auth_failed"/"error" control messages all carry
# `ev: "status"` — the actual state is in a separate `status` field, e.g.
# `{"ev":"status","status":"connected","message":"..."}`. The original code
# here checked `msg.get("ev") == "connected"` etc, which never matched (ev is
# always the literal string "status" for these), so auth was NEVER sent and
# every connection just sat idle until Polygon's ping-timeout silently killed
# it ~60s later — forever, in the reconnect loop visible in every session's
# logs. Fixed below to check `status`, not `ev`. `ev` is still the right field
# for actual market-data messages (T/Q/AM/O), which don't use this status
# envelope at all.
class _WSFeedBase:
    """Shared connect/backoff/circuit-breaker state for the stocks and options feeds."""

    def __init__(self, name: str):
        self.name = name
        self.running = False
        self._ws = None
        self.consecutive_failures = 0
        self.circuit_open_until = None
        self.last_message_ts = None
        self.last_status = "disconnected"  # disconnected | connecting | subscribed | circuit_open
        self.last_error = None

    async def start(self):
        self.running = True
        backoff = 1
        while self.running:
            if self.circuit_open_until and time.time() < self.circuit_open_until:
                remaining = self.circuit_open_until - time.time()
                self.last_status = "circuit_open"
                await asyncio.sleep(min(remaining, 30))
                continue

            self.last_status = "connecting"
            reached_live_data = False
            try:
                reached_live_data = await self._connect()
                backoff = 1
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"[{self.name}] Disconnected: {e}. Reconnect in {backoff}s")

            if reached_live_data:
                self.consecutive_failures = 0
                self.circuit_open_until = None
            else:
                self.consecutive_failures += 1
                if self.consecutive_failures >= WS_CIRCUIT_BREAKER_THRESHOLD:
                    self.circuit_open_until = time.time() + WS_CIRCUIT_BREAKER_COOLDOWN
                    logger.error(
                        f"[{self.name}] Circuit breaker tripped after "
                        f"{self.consecutive_failures} consecutive failures — "
                        f"cooling down for {WS_CIRCUIT_BREAKER_COOLDOWN}s"
                    )
                    self.consecutive_failures = 0
                    continue

            self.last_status = "disconnected"
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def stop(self):
        self.running = False
        if self._ws:
            await self._ws.close()

    def health(self) -> dict:
        return {
            "running": self.running,
            "state": self.last_status,
            "last_message_ts": self.last_message_ts,
            "consecutive_failures": self.consecutive_failures,
            "circuit_open": bool(self.circuit_open_until and time.time() < self.circuit_open_until),
            "last_error": self.last_error,
        }

    async def _recv_loop(self, ws, on_status, on_market_msg):
        """
        Shared receive loop: times out if nothing arrives for WS_RECV_TIMEOUT
        seconds (surfacing a stall immediately in logs, rather than waiting
        for the underlying ping-timeout to kill the connection silently ~60s
        later) and logs every raw status/error frame at INFO so entitlement
        or auth issues are visible instead of silently swallowed.
        Returns True once at least one real market-data message has been
        received (the only condition that resets the circuit breaker).
        """
        reached_live_data = False
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(f"[{self.name}] No message received in {WS_RECV_TIMEOUT}s — treating as stalled")
                return reached_live_data
            messages = json.loads(raw)
            for msg in messages:
                ev = msg.get("ev")
                if ev == "status":
                    logger.debug(f"[{self.name}] raw status frame: {msg}")
                    stop = await on_status(ws, msg)
                    if stop:
                        return reached_live_data
                else:
                    self.last_message_ts = time.time()
                    reached_live_data = True
                    self.last_status = "subscribed"
                    await on_market_msg(msg)


# ════════════════════════════════════════════════════════════════
# WEBSOCKET — STOCKS FEED
# ════════════════════════════════════════════════════════════════

class PolygonStocksWS(_WSFeedBase):
    """
    Maintains a persistent WebSocket connection to Polygon stocks feed.
    On each message, updates Redis and publishes to the 'quotes' pub/sub channel.
    Auto-reconnects with exponential backoff + a circuit breaker (see _WSFeedBase).
    """

    def __init__(self, symbols: list[str] = None):
        super().__init__("Polygon WS Stocks")
        self.symbols = symbols or DEFAULT_WATCHLIST

    async def _connect(self) -> bool:
        logger.info(f"[{self.name}] Connecting -> {POLYGON_WS_STOCKS}")
        async with websockets.connect(POLYGON_WS_STOCKS, ping_interval=20) as ws:
            self._ws = ws

            async def on_status(ws, msg):
                status = msg.get("status")
                if status == "connected":
                    await ws.send(json.dumps({"action": "auth", "params": POLYGON_API_KEY}))
                elif status == "auth_success":
                    subs = ",".join(
                        [f"T.{s}" for s in self.symbols]
                        + [f"Q.{s}" for s in self.symbols]
                        + [f"AM.{s}" for s in self.symbols]
                    )
                    await ws.send(json.dumps({"action": "subscribe", "params": subs}))
                    logger.info(f"[{self.name}] Subscribed to {len(self.symbols)} symbols")
                elif status == "auth_failed":
                    self.last_error = "auth_failed"
                    logger.error(f"[{self.name}] Auth failed — check API key")
                    return True
                elif status == "error":
                    self.last_error = msg.get("message")
                    logger.error(f"[{self.name}] Error from Polygon: {msg.get('message')}")
                    # An error status (e.g. "not authorized") is a permanent
                    # rejection for this connection attempt, not a transient
                    # blip — stop immediately instead of waiting out the full
                    # WS_RECV_TIMEOUT stall window before the caller retries.
                    return True
                return False

            return await self._recv_loop(ws, on_status, self._handle_market_msg)

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

class PolygonOptionsWS(_WSFeedBase):
    """
    Connects to Polygon options feed for real-time options quotes.

    Subscription-format note: the previous code subscribed to `O:{underlying}`
    (e.g. "O:AAPL") — but Polygon's options WS subscribes to actual per-contract
    tickers (e.g. "O:AAPL250117C00150000"), not underlyings. Fixed below to
    fetch each underlying's near-the-money contracts (nearest expirations,
    capped count) via the existing fetch_options_snapshot() and subscribe to
    those specific tickers. NOTE: this could not be verified end-to-end today
    because the account currently lacks real-time entitlement (see the
    _WSFeedBase docstring above) — Polygon rejects the subscribe call before
    any contract-level behavior can be observed. Re-verify once entitlement
    is confirmed active.
    """

    def __init__(self, symbols: list[str] = None):
        super().__init__("Polygon WS Options")
        self.symbols = symbols or DEFAULT_WATCHLIST

    async def _contract_tickers(self, max_per_underlying: int = 20) -> list[str]:
        tickers = []
        for sym in self.symbols:
            try:
                chain = await fetch_options_snapshot(sym)
            except Exception as e:
                logger.warning(f"[{self.name}] couldn't fetch chain for {sym}: {e}")
                continue
            if not chain:
                continue
            # Nearest expiration only, sorted by |strike - underlying last price|
            # so we subscribe to the most relevant near-the-money contracts
            # rather than an entire (potentially huge) chain.
            exps = sorted({c.get("details", {}).get("expiration_date") for c in chain if c.get("details")})
            if not exps:
                continue
            nearest_exp = exps[0]
            candidates = [c for c in chain if c.get("details", {}).get("expiration_date") == nearest_exp]
            underlying_px = (candidates[0].get("underlying_asset", {}) or {}).get("price") if candidates else None
            if underlying_px:
                candidates.sort(key=lambda c: abs((c.get("details", {}).get("strike_price") or 0) - underlying_px))
            for c in candidates[:max_per_underlying]:
                t = c.get("details", {}).get("ticker")
                if t:
                    tickers.append(t)
        return tickers

    async def _connect(self) -> bool:
        logger.info(f"[{self.name}] Connecting -> {POLYGON_WS_OPTIONS}")
        async with websockets.connect(POLYGON_WS_OPTIONS, ping_interval=20) as ws:
            self._ws = ws

            async def on_status(ws, msg):
                status = msg.get("status")
                if status == "connected":
                    await ws.send(json.dumps({"action": "auth", "params": POLYGON_API_KEY}))
                elif status == "auth_success":
                    contract_tickers = await self._contract_tickers()
                    if not contract_tickers:
                        logger.warning(f"[{self.name}] no contract tickers resolved; nothing to subscribe to")
                        return True
                    # Quotes only — _handle_options_msg below expects quote-shaped
                    # fields (bp/ap/bs/as); trade messages (T.) have a different
                    # shape (p/s) that isn't handled here, so don't subscribe to them.
                    subs = ",".join(f"Q.{t}" for t in contract_tickers)
                    await ws.send(json.dumps({"action": "subscribe", "params": subs}))
                    logger.info(f"[{self.name}] Subscribed to {len(contract_tickers)} contracts")
                elif status == "auth_failed":
                    self.last_error = "auth_failed"
                    logger.error(f"[{self.name}] Auth failed — check API key")
                    return True
                elif status == "error":
                    self.last_error = msg.get("message")
                    logger.error(f"[{self.name}] Error from Polygon: {msg.get('message')}")
                    # An error status (e.g. "not authorized") is a permanent
                    # rejection for this connection attempt, not a transient
                    # blip — stop immediately instead of waiting out the full
                    # WS_RECV_TIMEOUT stall window before the caller retries.
                    return True
                return False

            return await self._recv_loop(ws, on_status, self._handle_options_msg)

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
