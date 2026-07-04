"""
services/short_interest_client.py — FINRA short interest (free, no API key)

Source: FINRA Rule 4560 requires member firms to report OTC equity short
positions; FINRA publishes the consolidated result via its public Query API
(api.finra.org/data/group/otcMarket/name/consolidatedShortInterest). No signup,
no API key. Settlement happens bi-monthly (mid-month + end-of-month, with a
~2 week reporting lag before FINRA posts it), and FINRA only keeps a rolling
~1 year of history online.

Fails gracefully — an unknown ticker or a FINRA outage returns
{available: False, reason: ...} rather than crashing the tab, matching the
convention in services/altdata_client.py.
"""
import asyncio
import datetime
import logging

import aiohttp

from cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

FINRA_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
TTL_SHORT_INTEREST = 43200  # 12h — bi-monthly data, no need to hammer FINRA


def _shift_weekend(d: datetime.date) -> datetime.date:
    """FINRA settlement dates that land on a weekend shift back to the preceding Friday."""
    if d.weekday() == 5:   # Saturday
        return d - datetime.timedelta(days=1)
    if d.weekday() == 6:   # Sunday
        return d - datetime.timedelta(days=2)
    return d


def _settlement_candidates(months_back: int = 14) -> list[str]:
    """
    FINRA short-interest settlement dates fall on the 15th and the last calendar
    day of each month (shifted off weekends). We don't have a holiday calendar,
    so a handful of candidates may 404/empty — that's expected and handled by
    the caller, which just skips them.
    Returns ISO date strings, most recent first, excluding future dates.
    """
    today = datetime.date.today()
    dates = set()
    y, m = today.year, today.month
    for _ in range(months_back):
        mid = _shift_weekend(datetime.date(y, m, 15))
        last_day = (datetime.date(y, 12, 31) if m == 12
                    else datetime.date(y, m + 1, 1) - datetime.timedelta(days=1))
        last_day = _shift_weekend(last_day)
        for d in (last_day, mid):
            if d <= today:
                dates.add(d.isoformat())
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return sorted(dates, reverse=True)


async def _query_finra(session: aiohttp.ClientSession, symbol: str, settlement_date: str) -> dict | None:
    body = {
        "limit": 1,
        "compareFilters": [
            {"compareType": "EQUAL", "fieldName": "symbolCode", "fieldValue": symbol},
            {"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": settlement_date},
        ],
    }
    try:
        async with session.post(FINRA_URL, json=body,
                                 headers={"Accept": "application/json"},
                                 timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return None
            rows = await r.json()
            return rows[0] if rows else None
    except Exception as e:
        logger.warning(f"[ShortInterest] FINRA query error for {symbol}@{settlement_date}: {e}")
        return None


async def fetch_short_interest(symbol: str) -> dict:
    """
    Latest FINRA consolidated short-interest settlement for `symbol`, plus a
    short trailing history. Free & keyless (FINRA Rule 4560 data).
    """
    symbol = symbol.upper()
    cache_key = f"short_interest:{symbol}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    candidates = _settlement_candidates()
    history = []
    try:
        async with aiohttp.ClientSession() as session:
            # Walk candidates most-recent-first. FINRA settles bi-monthly with a
            # ~2wk reporting lag, so the newest 1-2 candidates are often not yet
            # published — that's normal, we just keep walking backwards.
            for d in candidates:
                row = await _query_finra(session, symbol, d)
                if row:
                    history.append(row)
                    if len(history) >= 6:
                        break
    except Exception as e:
        result = {"available": False, "symbol": symbol,
                   "reason": f"FINRA request failed: {str(e)[:120]}"}
        return result

    if not history:
        result = {"available": False, "symbol": symbol,
                   "reason": "no FINRA short interest settlement found for this ticker "
                             "(may be delisted, non-US listed, or too new to have settled)"}
        await cache_set(cache_key, result, 3600)
        return result

    latest = history[0]
    out = {
        "available": True,
        "symbol": symbol,
        "settlement_date": latest.get("settlementDate"),
        "short_interest": latest.get("currentShortPositionQuantity"),
        "previous_short_interest": latest.get("previousShortPositionQuantity"),
        "change_pct": latest.get("changePercent"),
        "days_to_cover": latest.get("daysToCoverQuantity"),
        "avg_daily_volume": latest.get("averageDailyVolumeQuantity"),
        "history": [
            {
                "settlement_date": h.get("settlementDate"),
                "short_interest": h.get("currentShortPositionQuantity"),
                "days_to_cover": h.get("daysToCoverQuantity"),
                "change_pct": h.get("changePercent"),
            } for h in history
        ],
        "source": "FINRA Rule 4560 Consolidated Short Interest",
    }
    await cache_set(cache_key, out, TTL_SHORT_INTEREST)
    return out
