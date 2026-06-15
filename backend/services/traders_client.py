"""
services/traders_client.py — Notable traders' moves

Three sources, all free:
  1. Corporate insiders  — SEC EDGAR Form 4 (official, real-time-ish)
  2. Congress trades      — community house/senate stock-watcher datasets (GitHub)
  3. Hedge fund 13F       — SEC EDGAR Form 13F (official, quarterly, ~45-day lag)

Caveats noted inline. Congress data depends on a community project; 13F is lagged.
"""
import aiohttp
import logging
from cache.redis_client import cache_get, cache_set
from services.filings_client import get_cik

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Spark Terminal research@example.com"}
TTL = 1800


# ── 1. Corporate insider trades (SEC Form 4) ────────────────────────────────
async def fetch_insider_trades(ticker: str, limit: int = 30) -> dict:
    """Recent Form 4 (insider) filings for a ticker from EDGAR."""
    cache_key = f"insider:{ticker.upper()}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    cik = await get_cik(ticker)
    if not cik:
        return {"error": f"no CIK for {ticker}", "ticker": ticker.upper(), "trades": []}

    # EDGAR full-text submissions, filter to Form 4
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return {"error": f"SEC {r.status}", "ticker": ticker.upper(), "trades": []}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.error(f"[Insider] {ticker}: {e}")
        return {"error": str(e), "ticker": ticker.upper(), "trades": []}

    recent = data.get("filings", {}).get("recent", {})
    forms      = recent.get("form", [])
    dates      = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs       = recent.get("primaryDocument", [])

    trades = []
    for i in range(len(forms)):
        if forms[i] != "4":
            continue
        acc = accessions[i].replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
               f"{docs[i]}") if i < len(docs) else None
        trades.append({
            "form":        forms[i],
            "filing_date": dates[i] if i < len(dates) else None,
            "url":         url,
        })
        if len(trades) >= limit:
            break

    result = {
        "ticker": ticker.upper(),
        "name":   data.get("name", ""),
        "trades": trades,
        "note":   "Form 4 insider filings. Open the link for transaction detail.",
    }
    await cache_set(cache_key, result, TTL)
    return result


# ── 2. Congressional trades (community dataset) ─────────────────────────────
# House & Senate stock-watcher publish aggregated disclosures as JSON.
HOUSE_URL  = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"


async def fetch_congress_trades(chamber: str = "house", limit: int = 50,
                                ticker: str = None) -> dict:
    """
    Recent congressional stock transactions.
    chamber: 'house' | 'senate'. Optionally filter by ticker.
    NOTE: relies on the community stock-watcher datasets.
    """
    cache_key = f"congress:{chamber}:{ticker or 'all'}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    url = SENATE_URL if chamber == "senate" else HOUSE_URL
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    return {"error": f"source returned {r.status}", "chamber": chamber,
                            "trades": [], "note": "Congress data source unavailable."}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.warning(f"[Congress] {chamber}: {e}")
        return {"error": str(e), "chamber": chamber, "trades": [],
                "note": "Congress data depends on a community dataset; may be unavailable."}

    # Normalize fields (house vs senate schemas differ slightly)
    trades = []
    for t in (data if isinstance(data, list) else [])[:5000]:
        sym = (t.get("ticker") or "").upper()
        if ticker and sym != ticker.upper():
            continue
        trades.append({
            "representative": t.get("representative") or t.get("senator") or "Unknown",
            "ticker":         sym if sym and sym != "--" else None,
            "asset":          t.get("asset_description", ""),
            "type":           t.get("type", ""),       # purchase / sale
            "amount":         t.get("amount", ""),
            "date":           t.get("transaction_date") or t.get("disclosure_date"),
        })
        if len(trades) >= limit:
            break

    result = {
        "chamber": chamber,
        "trades":  trades,
        "note":    "Source: community house/senate stock-watcher datasets.",
    }
    await cache_set(cache_key, result, 3600)
    return result


# ── 3. Hedge fund 13F holdings (SEC EDGAR) ──────────────────────────────────
# A few well-known managers by CIK for quick access.
NOTABLE_FUNDS = {
    "berkshire":   {"cik": "0001067983", "name": "Berkshire Hathaway (Buffett)"},
    "bridgewater": {"cik": "0001350694", "name": "Bridgewater (Dalio)"},
    "renaissance": {"cik": "0001037389", "name": "Renaissance Technologies"},
    "pershing":    {"cik": "0001336528", "name": "Pershing Square (Ackman)"},
    "scion":       {"cik": "0001649339", "name": "Scion (Burry)"},
    "appaloosa":   {"cik": "0001656456", "name": "Appaloosa (Tepper)"},
}


async def fetch_13f_filings(fund_key: str = "berkshire") -> dict:
    """Recent 13F-HR filings for a notable fund."""
    fund = NOTABLE_FUNDS.get(fund_key)
    if not fund:
        return {"error": "unknown fund", "available": list(NOTABLE_FUNDS.keys())}

    cache_key = f"13f:{fund_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    cik = fund["cik"]
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            async with s.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return {"error": f"SEC {r.status}", "fund": fund["name"], "filings": []}
                data = await r.json(content_type=None)
    except Exception as e:
        logger.error(f"[13F] {fund_key}: {e}")
        return {"error": str(e), "fund": fund["name"], "filings": []}

    recent = data.get("filings", {}).get("recent", {})
    forms      = recent.get("form", [])
    dates      = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    docs       = recent.get("primaryDocument", [])

    filings = []
    for i in range(len(forms)):
        if not forms[i].startswith("13F"):
            continue
        acc = accessions[i].replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
               f"{docs[i]}") if i < len(docs) and docs[i] else \
              f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F"
        filings.append({
            "form":        forms[i],
            "filing_date": dates[i] if i < len(dates) else None,
            "url":         url,
        })
        if len(filings) >= 8:
            break

    result = {
        "fund":    fund["name"],
        "cik":     cik,
        "filings": filings,
        "note":    "13F holdings are filed quarterly with a ~45-day lag.",
    }
    await cache_set(cache_key, result, 86400)
    return result


def list_funds() -> dict:
    return {k: v["name"] for k, v in NOTABLE_FUNDS.items()}
