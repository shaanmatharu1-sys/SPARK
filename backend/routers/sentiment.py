"""
routers/sentiment.py — Fear & Greed Index + supply chain proxies
"""
from fastapi import APIRouter
from services.fear_greed import fetch_fear_greed
from services.fred_client import fetch_series

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

# Supply chain proxy FRED series
SUPPLY_CHAIN_SERIES = {
    "DCOILWTICO": "WTI Crude",
    "DCOILBRENTEU": "Brent Crude",
    "PCUOMFGOMFG": "PPI Manufacturing",
    "CSCICP03USM665S": "Consumer Confidence",
    "PERMIT": "Building Permits",
    "MRTSSM44X72USS": "Retail Sales",
}


@router.get("/fear-greed")
async def get_fear_greed():
    """GET /sentiment/fear-greed — CNN Fear & Greed with all sub-indicators."""
    return await fetch_fear_greed()


@router.get("/supply-chain")
async def get_supply_chain():
    """
    GET /sentiment/supply-chain
    FRED proxies for supply chain health:
    crude, PPI manufacturing, consumer confidence, retail sales.
    """
    import asyncio
    tasks = [fetch_series(sid, limit=3) for sid in SUPPLY_CHAIN_SERIES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for (sid, name), data in zip(SUPPLY_CHAIN_SERIES.items(), results):
        if isinstance(data, list) and data:
            current = data[0]
            prev    = data[1] if len(data) > 1 else None
            output[sid] = {
                "name":   name,
                "value":  current.get("value"),
                "date":   current.get("date"),
                "change": round(current["value"] - prev["value"], 4)
                          if prev and current.get("value") and prev.get("value") else None,
            }

    return output
