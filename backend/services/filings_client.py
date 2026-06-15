"""
services/filings_client.py — SEC EDGAR filings (free official API)
Fetches recent filings (10-K, 10-Q, 8-K, etc.) and company facts for a ticker.
Docs: https://www.sec.gov/edgar/sec-api-documentation
"""
import aiohttp
import logging
from cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

# SEC requires a descriptive User-Agent with contact info
HEADERS = {"User-Agent": "Spark Terminal research@example.com"}
TTL_FILINGS = 3600

# Ticker -> CIK mapping (SEC's official file)
_TICKER_CIK: dict[str, str] = {}


async def _load_ticker_cik():
    """Load and cache the SEC ticker->CIK map (large, cached aggressively)."""
    global _TICKER_CIK
    if _TICKER_CIK:
        return
    cached = await cache_get("sec:ticker_cik")
    if cached:
        _TICKER_CIK = cached
        return
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get("https://www.sec.gov/files/company_tickers.json",
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    # data is {idx: {cik_str, ticker, title}}
                    _TICKER_CIK = {
                        v["ticker"].upper(): str(v["cik_str"]).zfill(10)
                        for v in data.values()
                    }
                    await cache_set("sec:ticker_cik", _TICKER_CIK, 86400)
    except Exception as e:
        logger.error(f"[SEC] ticker map load failed: {e}")


async def get_cik(ticker: str) -> str | None:
    await _load_ticker_cik()
    return _TICKER_CIK.get(ticker.upper())


async def fetch_filings(ticker: str, limit: int = 20) -> dict:
    """Recent filings for a ticker."""
    cache_key = f"filings:{ticker.upper()}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    cik = await get_cik(ticker)
    if not cik:
        return {"error": f"no CIK found for {ticker}", "ticker": ticker.upper()}

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return {"error": f"SEC returned {r.status}", "ticker": ticker.upper()}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.error(f"[SEC] filings fetch failed: {e}")
        return {"error": str(e), "ticker": ticker.upper()}

    recent = data.get("filings", {}).get("recent", {})
    forms      = recent.get("form", [])
    dates      = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs       = recent.get("primaryDocument", [])
    descs      = recent.get("primaryDocDescription", [])

    filings = []
    for i in range(min(limit, len(forms))):
        acc_nodash = accessions[i].replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
               f"{acc_nodash}/{docs[i]}") if i < len(docs) and docs[i] else None
        filings.append({
            "form":        forms[i],
            "filing_date": dates[i] if i < len(dates) else None,
            "description": descs[i] if i < len(descs) else "",
            "url":         url,
        })

    result = {
        "ticker":  ticker.upper(),
        "name":    data.get("name", ""),
        "cik":     cik,
        "sic":     data.get("sicDescription", ""),
        "filings": filings,
    }
    await cache_set(cache_key, result, TTL_FILINGS)
    return result


async def fetch_filings_by_type(ticker: str, form_type: str = "10-K", limit: int = 5) -> dict:
    """Filings filtered to a specific form type (10-K, 10-Q, 8-K, etc.)."""
    all_filings = await fetch_filings(ticker, limit=100)
    if "error" in all_filings:
        return all_filings
    filtered = [f for f in all_filings["filings"]
                if f["form"].upper() == form_type.upper()][:limit]
    return {**all_filings, "filings": filtered, "form_type": form_type}
