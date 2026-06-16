"""
analytics/arbitrage/etf_engine.py

ETF vs underlying-holdings spread (premium/discount to intraday NAV proxy).

For a basket ETF, computes an intraday "fair value" from its top holdings and
their weights, then compares to the ETF's live price. A meaningful gap is a
premium (ETF trades above basket) or discount (below) — the classic ETF
arbitrage signal that authorized participants arbitrage away.

HONEST LIMITATIONS:
  - Uses TOP-N holdings (not the full basket), so the NAV proxy is approximate —
    it tracks the spread's *direction and changes*, not an exact creation-unit NAV.
  - Holdings/weights are curated snapshots (they drift slowly); not live-sourced.
  - Real AP arbitrage uses full baskets, FX, and fees we don't model.
  This is a *monitoring* tool for the premium/discount signal, not a trading system.
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

from cache.redis_client import cache_get, cache_set
from services.polygon_client import fetch_snapshot

# Curated top holdings + weights (%) for liquid ETFs. Weights are approximate
# snapshots; they drift slowly. Top holdings capture most of the basket variance.
ETF_HOLDINGS = {
    "XLK": {  # Technology Select Sector
        "name": "Technology Select Sector SPDR",
        "holdings": {"AAPL": 14.2, "MSFT": 13.8, "NVDA": 13.5, "AVGO": 5.1,
                     "ORCL": 3.0, "CRM": 2.6, "CSCO": 2.3, "ACN": 2.1,
                     "AMD": 2.0, "ADBE": 1.9},
    },
    "XLF": {  # Financials
        "name": "Financial Select Sector SPDR",
        "holdings": {"BRK-B": 13.0, "JPM": 10.2, "V": 7.8, "MA": 6.6,
                     "BAC": 4.4, "WFC": 3.6, "GS": 3.0, "SPGI": 2.7,
                     "AXP": 2.5, "MS": 2.3},
    },
    "XLE": {  # Energy
        "name": "Energy Select Sector SPDR",
        "holdings": {"XOM": 22.5, "CVX": 16.0, "COP": 7.8, "WMB": 4.6,
                     "EOG": 4.0, "SLB": 3.7, "MPC": 3.5, "PSX": 3.2,
                     "OKE": 3.1, "VLO": 2.8},
    },
    "XLV": {  # Health Care
        "name": "Health Care Select Sector SPDR",
        "holdings": {"LLY": 11.5, "UNH": 8.9, "JNJ": 7.0, "ABBV": 6.2,
                     "MRK": 4.8, "TMO": 3.9, "ABT": 3.7, "AMGN": 3.3,
                     "DHR": 3.0, "PFE": 2.9},
    },
    "QQQ": {  # Nasdaq 100 (top holdings only — large basket)
        "name": "Invesco QQQ Trust",
        "holdings": {"AAPL": 8.9, "MSFT": 8.2, "NVDA": 7.9, "AMZN": 5.5,
                     "AVGO": 4.8, "META": 4.6, "TSLA": 3.1, "GOOGL": 2.6,
                     "GOOG": 2.5, "COST": 2.7},
    },
    "DIA": {  # Dow Jones (price-weighted — approximation)
        "name": "SPDR Dow Jones Industrial Average",
        "holdings": {"UNH": 8.5, "GS": 7.4, "MSFT": 6.3, "HD": 6.0,
                     "CAT": 5.5, "CRM": 5.0, "V": 4.6, "AXP": 4.4,
                     "AMGN": 4.2, "MCD": 4.0},
    },
}


async def compute_etf_spread(etf: str):
    etf = etf.upper()
    meta = ETF_HOLDINGS.get(etf)
    if not meta:
        return {"error": f"{etf} not in covered ETFs",
                "covered": list(ETF_HOLDINGS.keys())}

    holdings = meta["holdings"]
    symbols = [etf] + list(holdings.keys())
    snap = await fetch_snapshot(symbols)

    def last_price(sym):
        d = snap.get(sym, {})
        return ((d.get("lastTrade", {}) or {}).get("p")
                or (d.get("day", {}) or {}).get("c")
                or (d.get("prevDay", {}) or {}).get("c"))

    def pct_change(sym):
        return snap.get(sym, {}).get("todaysChangePerc")

    etf_px = last_price(etf)
    if not etf_px:
        return {"error": f"no price for {etf}"}

    # Build a basket index: weighted % change of holdings vs ETF % change.
    # Since we don't have share counts, we compare today's weighted-return of the
    # basket to the ETF's return — the divergence is the intraday premium/discount drift.
    total_w = sum(holdings.values())
    basket_ret = 0.0
    covered_w = 0.0
    comps = []
    for sym, w in holdings.items():
        pc = pct_change(sym)
        px = last_price(sym)
        if pc is None:
            continue
        basket_ret += (w / total_w) * pc
        covered_w += w
        comps.append({"symbol": sym, "weight": w, "change_pct": round(pc, 2),
                      "price": round(px, 2) if px else None})

    etf_ret = pct_change(etf)
    if etf_ret is None:
        return {"error": f"no intraday change for {etf}"}

    # Spread = ETF return − basket return (in pct points). Positive = ETF
    # outpacing its basket (premium building); negative = lagging (discount).
    spread = round(etf_ret - basket_ret, 3)

    comps.sort(key=lambda c: -c["weight"])
    return {
        "etf": etf, "name": meta["name"],
        "etf_price": round(etf_px, 2),
        "etf_change_pct": round(etf_ret, 2),
        "basket_change_pct": round(basket_ret, 2),
        "spread_pct": spread,
        "signal": ("premium" if spread > 0.05 else
                   "discount" if spread < -0.05 else "fair"),
        "coverage_pct": round(covered_w, 1),
        "holdings": comps,
        "as_of": datetime.datetime.utcnow().isoformat(),
    }


async def scan_all_etfs():
    cache_key = "arb:etf_scan"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    results = await asyncio.gather(*[compute_etf_spread(e) for e in ETF_HOLDINGS])
    rows = [r for r in results if "error" not in r]
    rows.sort(key=lambda r: -abs(r["spread_pct"]))
    out = {"etfs": rows, "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, out, ttl=30)
    return out
