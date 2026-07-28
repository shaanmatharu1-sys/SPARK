"""
routers/weather.py — Weather-driven commodity futures research endpoints.

Regions are hand-picked for what they mean to specific futures contracts
(drought in Iowa -> corn/soy, freezes in the Permian -> WTI crude, etc) —
see services/weather_client.py's REGIONS dict for the full mapping and the
one-line rationale for each region.
"""
from fastapi import APIRouter
from services.weather_client import fetch_all_regions, fetch_region_current, REGIONS

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/regions")
async def regions():
    """All tracked regions: current conditions, 7-day forecast, vs-normal anomaly, linked futures."""
    return await fetch_all_regions()


@router.get("/{region_key}")
async def region_detail(region_key: str):
    """Single region detail. region_key is one of services/weather_client.py's REGIONS keys."""
    if region_key not in REGIONS:
        return {"error": f"unknown region '{region_key}'", "regions": list(REGIONS.keys())}
    return await fetch_region_current(region_key)
