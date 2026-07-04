"""
services/traders_client.py — Notable traders' moves

Three sources, all free:
  1. Corporate insiders  — SEC EDGAR Form 4 (official, real-time-ish)
  2. Congress trades      — community house/senate stock-watcher datasets (GitHub)
  3. Hedge fund 13F       — SEC EDGAR Form 13F (official, quarterly, ~45-day lag)

Form 4 and 13F filings are parsed down to the actual structured data (transactions /
holdings), not just links to the filing — see _fetch_form4_detail and
_fetch_13f_holdings. As elsewhere in this codebase: fail gracefully, return what you
have, note what's missing. A single unparseable filing must never break the response.

Caveats noted inline. Congress data depends on a community project; 13F is lagged.
"""
import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
from cache.redis_client import cache_get, cache_set
from services.filings_client import get_cik

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Spark Terminal research@example.com"}
TTL = 1800
DOC_TTL = 30 * 86400          # parsed filing documents are immutable once filed
MAX_CONCURRENT_FETCHES = 5     # be a good citizen re: SEC's ~10 req/sec rate limit

# Form 4 transaction codes -> human labels (most common; see SEC Form 4 instructions)
TXN_CODE_LABELS = {
    "P": "Open market buy", "S": "Open market sale", "A": "Grant/award",
    "D": "Disposition to issuer", "F": "Tax withholding", "M": "Option exercise",
    "G": "Gift", "V": "Voluntary report", "C": "Conversion", "X": "In-the-money exercise",
    "W": "Will/inheritance", "Z": "Trust transaction", "J": "Other",
    "K": "Equity swap", "U": "Tender of shares",
}


def _strip_ns(elem: ET.Element) -> ET.Element:
    """Strip XML namespaces from every tag so plain (no-prefix) XPath works."""
    for el in elem.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return elem


def _text(el, path):
    node = el.find(path)
    return node.text.strip() if node is not None and node.text else None


def _num(el, path):
    v = _text(el, path)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ── 1. Corporate insider trades (SEC Form 4) ────────────────────────────────
def _parse_form4_xml(xml_text: str) -> dict | None:
    """Parse a raw Form 4 ownership XML into owner info + transaction list."""
    try:
        root = _strip_ns(ET.fromstring(xml_text))
    except ET.ParseError:
        return None

    owner = root.find(".//reportingOwner")
    if owner is None:
        return None
    owner_name = _text(owner, ".//rptOwnerName") or "Unknown"
    rel = owner.find("reportingOwnerRelationship")
    roles = []
    officer_title = None
    if rel is not None:
        def _truthy(tag):
            v = _text(rel, tag)
            return v is not None and v.lower() in ("true", "1")
        if _truthy("isDirector"):
            roles.append("Director")
        if _truthy("isOfficer"):
            officer_title = _text(rel, "officerTitle")
            roles.append(f"Officer ({officer_title})" if officer_title else "Officer")
        if _truthy("isTenPercentOwner"):
            roles.append("10% Owner")
        if _truthy("isOther"):
            roles.append(_text(rel, "otherText") or "Other")
    relationship = ", ".join(roles) or "Reporting person"

    transactions = []
    for is_derivative, table, txn_tag in (
        (False, "nonDerivativeTable", "nonDerivativeTransaction"),
        (True, "derivativeTable", "derivativeTransaction"),
    ):
        for t in root.findall(f".//{table}/{txn_tag}"):
            code = _text(t, ".//transactionCoding/transactionCode")
            shares = _num(t, ".//transactionAmounts/transactionShares/value")
            price = _num(t, ".//transactionAmounts/transactionPricePerShare/value")
            transactions.append({
                "security":       _text(t, ".//securityTitle/value"),
                "date":           _text(t, ".//transactionDate/value"),
                "code":           code,
                "code_label":     TXN_CODE_LABELS.get(code, code),
                "shares":         shares,
                "price":          price,
                "value":          round(shares * price, 2) if shares and price else None,
                "acquired_disposed": _text(t, ".//transactionAmounts/transactionAcquiredDisposedCode/value"),
                "shares_owned_after": _num(t, ".//postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
                "derivative":     is_derivative,
            })

    return {"owner_name": owner_name, "relationship": relationship, "transactions": transactions}


async def _fetch_form4_detail(session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                              cik: str, accession: str, primary_doc: str) -> dict | None:
    """Fetch + parse one Form 4's raw XML, caching the parsed result indefinitely."""
    acc = accession.replace("-", "")
    cache_key = f"form4doc:{acc}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached or None

    # primaryDocument is often "xslF345X06/form4.xml" — that path is an HTML
    # rendering of the raw XML. The raw XML itself lives at the accession root
    # under the same basename, without the xsl.../ viewer prefix.
    basename = primary_doc.rsplit("/", 1)[-1] if primary_doc else None
    if not basename:
        return None
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{basename}"

    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    await cache_set(cache_key, {}, 3600)
                    return None
                xml_text = await r.text()
        except Exception as e:
            logger.warning(f"[Insider] fetch {url}: {e}")
            return None

    parsed = _parse_form4_xml(xml_text)
    await cache_set(cache_key, parsed or {}, DOC_TTL)
    return parsed


async def fetch_insider_trades(ticker: str, limit: int = 30) -> dict:
    """Recent Form 4 (insider) filings for a ticker, with parsed transaction detail."""
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

    filings = []
    for i in range(len(forms)):
        if forms[i] != "4":
            continue
        acc = accessions[i].replace("-", "")
        doc = docs[i] if i < len(docs) else None
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}") if doc else None
        filings.append({
            "form":         forms[i],
            "filing_date":  dates[i] if i < len(dates) else None,
            "accession":    accessions[i],
            "primary_doc":  doc,
            "url":          url,
        })
        if len(filings) >= limit:
            break

    # Fetch + parse the underlying XML for each filing concurrently (capped).
    trades = []
    unparsed = 0
    if filings:
        sem = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            details = await asyncio.gather(*[
                _fetch_form4_detail(s, sem, cik, f["accession"], f["primary_doc"])
                for f in filings
            ], return_exceptions=True)

        for f, detail in zip(filings, details):
            if isinstance(detail, Exception) or not detail:
                unparsed += 1
                continue
            for txn in detail["transactions"]:
                trades.append({
                    "name":         detail["owner_name"],
                    "relationship": detail["relationship"],
                    "form":         f["form"],
                    "filing_date":  f["filing_date"],
                    "url":          f["url"],
                    **txn,
                })

    note = "Form 4 insider transactions, parsed from SEC EDGAR XML."
    if unparsed:
        note += f" ({unparsed} of {len(filings)} filings could not be parsed and were skipped.)"

    result = {
        "ticker": ticker.upper(),
        "name":   data.get("name", ""),
        "trades": trades,
        "note":   note,
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


MAX_HOLDINGS = 200   # some quant funds hold thousands of positions; cap the payload


def _parse_13f_infotable_xml(xml_text: str) -> list[dict] | None:
    """Parse a 13F information-table XML into a list of per-holding dicts."""
    try:
        root = _strip_ns(ET.fromstring(xml_text))
    except ET.ParseError:
        return None

    # NOTE: SEC's 13F "value" convention changed with the 2023 technical amendments
    # (schema X0202+): value is now reported in whole dollars. Older filings
    # (schema X01/X02) reported value in thousands. We only ever parse the most
    # recent filing(s), which use the current schema, so no thousands scaling here.
    holdings = []
    for row in root.findall(".//infoTable"):
        holdings.append({
            "issuer":          _text(row, "nameOfIssuer"),
            "class":           _text(row, "titleOfClass"),
            "cusip":           _text(row, "cusip"),
            "value_usd":       _num(row, "value"),
            "shares":          _num(row, "shrsOrPrnAmt/sshPrnamt"),
            "share_type":      _text(row, "shrsOrPrnAmt/sshPrnamtType"),
            "investment_discretion": _text(row, "investmentDiscretion"),
        })
    holdings.sort(key=lambda h: h["value_usd"] or 0, reverse=True)
    return holdings


async def _fetch_13f_holdings(session: aiohttp.ClientSession, cik: str, accession: str) -> list[dict] | None:
    """
    Find and parse the information-table XML for one 13F accession.
    The primaryDocument (primary_doc.xml) is just the cover page — the actual
    holdings live in a sibling XML file, whose name varies filing to filing, so
    we list the accession's index.json to find it.
    """
    acc = accession.replace("-", "")
    cache_key = f"13fdoc:{acc}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached or None

    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}"
    try:
        async with session.get(f"{base}/index.json", timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                await cache_set(cache_key, [], 3600)
                return None
            idx = await r.json(content_type=None)
    except Exception as e:
        logger.warning(f"[13F] index.json {acc}: {e}")
        return None

    items = idx.get("directory", {}).get("item", [])
    infotable_name = next(
        (it["name"] for it in items
         if it.get("name", "").lower().endswith(".xml")
         and "primary_doc" not in it.get("name", "").lower()),
        None,
    )
    if not infotable_name:
        await cache_set(cache_key, [], 3600)
        return None

    try:
        async with session.get(f"{base}/{infotable_name}",
                               timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                await cache_set(cache_key, [], 3600)
                return None
            xml_text = await r.text()
    except Exception as e:
        logger.warning(f"[13F] infotable fetch {acc}: {e}")
        return None

    holdings = _parse_13f_infotable_xml(xml_text)
    await cache_set(cache_key, holdings or [], DOC_TTL)
    return holdings


async def fetch_13f_filings(fund_key: str = "berkshire") -> dict:
    """Recent 13F-HR filings for a notable fund, with parsed holdings for the latest one."""
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
            "accession":   accessions[i],
            "url":         url,
        })
        if len(filings) >= 8:
            break

    # Parse holdings for the most recent filing that actually carries an
    # information table (13F-HR / 13F-HR/A — a 13F-NT is just a "filed by
    # another manager" notice with no holdings of its own).
    holdings = []
    holdings_note = None
    target = next((f for f in filings if f["form"] in ("13F-HR", "13F-HR/A")), None)
    if target:
        async with aiohttp.ClientSession(headers=HEADERS) as s:
            parsed = await _fetch_13f_holdings(s, cik, target["accession"])
        if parsed:
            truncated = len(parsed) > MAX_HOLDINGS
            holdings = parsed[:MAX_HOLDINGS]
            holdings_note = (f"Top {MAX_HOLDINGS} of {len(parsed)} holdings by value, "
                             f"from the {target['filing_date']} {target['form']} filing.") \
                            if truncated else \
                            f"{len(parsed)} holdings from the {target['filing_date']} {target['form']} filing."
        else:
            holdings_note = f"Could not parse holdings for the {target['filing_date']} filing."

    result = {
        "fund":          fund["name"],
        "cik":           cik,
        "filings":       filings,
        "holdings":      holdings,
        "holdings_note": holdings_note,
        "note":          "13F holdings are filed quarterly with a ~45-day lag.",
    }
    await cache_set(cache_key, result, 86400)
    return result


def list_funds() -> dict:
    return {k: v["name"] for k, v in NOTABLE_FUNDS.items()}
