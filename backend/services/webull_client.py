"""
services/webull_client.py — Crypto market data via the Webull OpenAPI.

Stopgap for the crypto board's coin coverage: Polygon's and Coinbase's crypto
feeds (services/polygon_client.py, services/coinbase_ws_client.py) are both
hardcoded to 4 symbols (BTC, ETH, SOL, DOGE). Webull's OpenAPI crypto
endpoints need no market-data subscription (unlike its US stock/options/
futures endpoints, which do), so they're used here purely to widen the board
— snapshot pricing for however many crypto instruments Webull lists, not a
replacement for Polygon/Coinbase.

Confirmed against the SDK's own source (github.com/webull-inc/
webull-openapi-python-sdk), not just the docs site, since the docs were
inconsistent about method names:
  - DataClient.instrument.get_crypto_instrument() lists tradable symbols.
  - DataClient.crypto_market_data.get_crypto_snapshot(symbols) — up to 20
    symbols per call, 1 req/sec per App Key, 600 req/min account-wide.
  - No tick/depth-of-book methods exist for crypto in this SDK version —
    snapshot + history bars is the full free surface.

The SDK is synchronous (built on `requests`), so calls are wrapped in
asyncio.to_thread to avoid blocking the event loop.
"""
import asyncio
import logging

from cache.redis_client import cache_get, cache_set
from config import (
    WEBULL_APP_KEY,
    WEBULL_APP_SECRET,
    WEBULL_REGION,
    TTL_CRYPTO_WEBULL,
    TTL_CRYPTO_INSTRUMENTS,
)

logger = logging.getLogger(__name__)

# Webull's own snapshot request cap.
_MAX_SYMBOLS_PER_CALL = 20
# Cap how many symbols the default (no-args) snapshot call covers, so a cold
# cache doesn't serialize N/20 sequential 1-req/sec calls into a slow board.
_MAX_DEFAULT_SYMBOLS = 60

_data_client = None
_client_init_failed = False


def _get_data_client():
    """Lazily build the SDK's DataClient. Returns None if unconfigured."""
    global _data_client, _client_init_failed
    if _data_client is not None:
        return _data_client
    if _client_init_failed:
        return None
    if not WEBULL_APP_KEY or not WEBULL_APP_SECRET:
        _client_init_failed = True
        logger.info("Webull OpenAPI not configured (WEBULL_APP_KEY/SECRET unset) — crypto board stays Polygon/Coinbase-only")
        return None
    try:
        from webull.core.client import ApiClient
        from webull.data.data_client import DataClient
        api_client = ApiClient(WEBULL_APP_KEY, WEBULL_APP_SECRET, WEBULL_REGION)
        _data_client = DataClient(api_client)
        return _data_client
    except ImportError:
        _client_init_failed = True
        logger.warning("webull-openapi-python-sdk not installed — crypto board stays Polygon/Coinbase-only")
        return None
    except Exception as e:
        _client_init_failed = True
        logger.warning(f"Webull OpenAPI client init failed: {str(e)[:200]}")
        return None


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def fetch_crypto_instruments() -> list[str]:
    """All symbols Webull's OpenAPI lists for crypto (e.g. ['BTCUSD', 'ETHUSD', ...])."""
    cache_key = "webull:crypto:instruments"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_data_client()
    if client is None:
        return []

    def _blocking():
        from webull.data.common.category import Category
        res = client.instrument.get_crypto_instrument(category=Category.US_CRYPTO.name, page_size=1000)
        if res.status_code != 200:
            return []
        body = res.json()
        items = body.get("data") or body.get("items") or body.get("list") or body if isinstance(body, list) else []
        symbols = []
        for item in items if isinstance(items, list) else []:
            sym = _pick(item, "symbol", "instrument_id")
            if sym:
                symbols.append(sym)
        return symbols

    try:
        symbols = await asyncio.to_thread(_blocking)
    except Exception as e:
        logger.warning(f"Webull get_crypto_instrument failed: {str(e)[:200]}")
        symbols = []

    await cache_set(cache_key, symbols, TTL_CRYPTO_INSTRUMENTS)
    return symbols


def _parse_snapshot_item(item: dict) -> dict | None:
    sym = _pick(item, "symbol", "instrument_id")
    if not sym:
        return None
    price = _to_float(_pick(item, "price", "close", "last_price", "latest_price"))
    prev_close = _to_float(_pick(item, "pre_close", "prev_close"))
    # "change_ratio" is a fraction (0.0123 == 1.23%, per screener.py's field
    # docs in the SDK source); "change_pct" (if ever present) is already a
    # percent. Branch on which key matched rather than guessing from
    # magnitude — a genuine small percent move is indistinguishable from a
    # fraction by size alone.
    ratio = _to_float(_pick(item, "change_ratio", "changeRatio"))
    if ratio is not None:
        change_pct = round(ratio * 100, 2)
    else:
        change_pct = _to_float(_pick(item, "change_pct"))
    if change_pct is None and price is not None and prev_close:
        change_pct = round((price - prev_close) / prev_close * 100, 2)
    return {
        "symbol":     sym,
        "price":      price,
        "change_pct": change_pct,
        "high":       _to_float(_pick(item, "high")),
        "low":        _to_float(_pick(item, "low")),
        "volume":     _to_float(_pick(item, "volume")),
        "prev_close": prev_close,
        "source":     "webull",
    }


async def fetch_crypto_snapshot(symbols: list[str] = None) -> dict:
    """
    Crypto snapshots keyed by symbol, shaped to match
    polygon_client.fetch_crypto_snapshot()'s output so callers/frontend can
    treat the two interchangeably.
    """
    cache_key = f"webull:crypto:snapshot:{','.join(symbols)}" if symbols else "webull:crypto:snapshot:default"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    client = _get_data_client()
    if client is None:
        return {}

    if not symbols:
        symbols = await fetch_crypto_instruments()
        symbols = symbols[:_MAX_DEFAULT_SYMBOLS]
    if not symbols:
        return {}

    def _fetch_batch(batch: list[str]):
        from webull.data.common.category import Category
        res = client.crypto_market_data.get_crypto_snapshot(batch, category=Category.US_CRYPTO.name)
        if res.status_code != 200:
            return []
        body = res.json()
        items = body.get("data") or body.get("items") or body.get("list") or (body if isinstance(body, list) else [])
        return items if isinstance(items, list) else []

    result = {}
    batches = [symbols[i:i + _MAX_SYMBOLS_PER_CALL] for i in range(0, len(symbols), _MAX_SYMBOLS_PER_CALL)]
    for i, batch in enumerate(batches):
        try:
            items = await asyncio.to_thread(_fetch_batch, batch)
            for item in items:
                parsed = _parse_snapshot_item(item)
                if parsed:
                    result[parsed["symbol"]] = parsed
        except Exception as e:
            logger.warning(f"Webull get_crypto_snapshot batch failed: {str(e)[:200]}")
        # Free tier is 1 req/sec per App Key — only sleep between batches.
        if i < len(batches) - 1:
            await asyncio.sleep(1)

    await cache_set(cache_key, result, TTL_CRYPTO_WEBULL)
    return result
