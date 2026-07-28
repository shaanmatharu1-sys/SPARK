"""
services/weather_client.py — Open-Meteo weather/climate data for the regions
that actually move commodity futures prices: drought/frost hits grain and
coffee, heating/cooling demand drives natural gas, hurricanes and freezes hit
Gulf Coast / Permian oil & gas infrastructure. This is deliberately NOT a
generic weather widget — every region below is tagged with the futures
contract(s) (from services/futures_client.py's FUTURES dict) it's a trading
signal for.

Open-Meteo is completely free, no API key, no signup, generous free tier:
  - Forecast API  (api.open-meteo.com/v1/forecast):    current conditions +
    7-day daily forecast for a lat/lon.
  - Archive API   (archive-api.open-meteo.com/v1/archive): historical daily
    observations. Used here to build a same-day-of-year climate "normal"
    (a plain mean over the trailing 10 years, +/- a few day window), so
    today's conditions can be expressed as an anomaly ("+4.2F vs normal",
    "-30% precip vs normal") — that's the actually-useful trading signal,
    not the raw temperature.

Response shape verified live against the real API (2026-07-26):
  forecast:  {"current": {temperature_2m, precipitation, wind_speed_10m,
              weather_code, time}, "daily": {time: [...], temperature_2m_max:
              [...], temperature_2m_min: [...], precipitation_sum: [...],
              precipitation_probability_max: [...]}}
  archive:   {"daily": {time: [...], temperature_2m_max: [...],
              temperature_2m_min: [...], precipitation_sum: [...]}}
Note it's `current`, not the older `current_weather` some docs/examples show.
"""
import asyncio
import datetime
import logging

logger = logging.getLogger(__name__)

import aiohttp

from cache.redis_client import cache_get, cache_set
from config import TTL_WEATHER

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"

# Region -> the futures contract(s) it's a trading signal for, cross-referenced
# against services/futures_client.py's FUTURES dict (ZC=F corn, ZS=F soybeans,
# ZW=F wheat, CL=F WTI crude, NG=F natural gas all already exist there).
REGIONS = {
    "corn_belt": {
        "name": "US Corn Belt (Iowa)", "lat": 42.0, "lon": -93.5,
        "futures": ["ZC=F", "ZS=F"],
        "risk": "Drought/heat stress during pollination and grain fill hits corn and soybean yields",
    },
    "wheat_belt": {
        "name": "US Wheat Belt (Kansas)", "lat": 38.5, "lon": -98.0,
        "futures": ["ZW=F"],
        "risk": "Freeze and drought risk to winter wheat development on the Southern Plains",
    },
    "gulf_coast": {
        "name": "US Gulf Coast / Henry Hub (Louisiana)", "lat": 29.9, "lon": -93.3,
        "futures": ["NG=F"],
        "risk": "Hurricane and cold-snap risk to Gulf Coast gas production, processing, and LNG export terminals",
    },
    "permian": {
        "name": "Permian Basin (West Texas)", "lat": 31.9, "lon": -102.3,
        "futures": ["CL=F"],
        "risk": "Winter freeze risk to wellhead and pipeline crude production (see the Feb 2021 Texas freeze-off)",
    },
    "midwest_chicago": {
        "name": "Midwest / Chicago", "lat": 41.9, "lon": -87.6,
        "futures": ["NG=F"],
        "risk": "Heating degree days across the populous Midwest drive winter natural gas demand",
    },
    "mato_grosso": {
        "name": "Mato Grosso, Brazil", "lat": -12.6, "lon": -55.9,
        "futures": ["ZS=F", "ZC=F"],
        "risk": "World's largest soybean-exporting state and a major corn producer — planting/harvest rainfall is the key swing factor",
    },
    "pampas": {
        "name": "Buenos Aires Pampas, Argentina", "lat": -34.6, "lon": -63.6,
        "futures": ["ZS=F", "ZC=F"],
        "risk": "Argentina's core soy/corn belt — La Nina-driven drought is a recurring supply shock",
    },
    "black_sea": {
        "name": "Black Sea / Ukraine Wheat Belt", "lat": 49.0, "lon": 32.0,
        "futures": ["ZW=F"],
        "risk": "War-exposed wheat-exporting region — adverse weather compounds an already fragile supply chain",
    },
    "brazil_coffee": {
        "name": "Minas Gerais, Brazil (Coffee Belt)", "lat": -19.0, "lon": -45.0,
        "futures": None,
        "futures_note": "Coffee (KC=F) isn't a covered contract in this app's futures universe yet — tracked anyway as a frost/drought signal region",
        "risk": "Frost and drought in Brazil's main Arabica-growing region are the classic coffee-price shock",
    },
}

# WMO weather codes (subset actually returned by Open-Meteo's `weather_code`) -> label
WEATHER_CODE_DESC = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Severe thunderstorm w/ hail",
}

WINDOW_DAYS = 5  # +/- N calendar days around today's day-of-year, for the climate-normal sample


def _pct_diff(actual, normal):
    if actual is None or normal in (None, 0):
        return None
    return round((actual - normal) / abs(normal) * 100, 1)


async def _fetch_json(session, url, params):
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} from {url.split('/v1/')[0]}")
        return await r.json()


async def _fetch_forecast(session, lat, lon):
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 7,
        "temperature_unit": "fahrenheit", "precipitation_unit": "inch", "wind_speed_unit": "mph",
    }
    return await _fetch_json(session, FORECAST_URL, params)


async def _fetch_normal(session, lat, lon):
    """
    ~10yr same-day-of-year climate normal via the Archive API. One call spans
    the full 10-year range (fast in practice — ~1s observed for ~3650 daily
    rows), then we average just the +/- WINDOW_DAYS days around today's
    day-of-year across all of those years. Deliberately simple: a plain mean,
    no fitted climatology — that's all this trading signal needs.
    """
    today = datetime.date.today()
    end_year = today.year - 1
    start_year = end_year - 9  # 10 full calendar years of history
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{start_year}-01-01", "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "temperature_unit": "fahrenheit", "precipitation_unit": "inch",
    }
    data = await _fetch_json(session, ARCHIVE_URL, params)
    daily = data.get("daily") or {}
    times  = daily.get("time") or []
    tmax   = daily.get("temperature_2m_max") or []
    tmin   = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []

    target_yday = today.timetuple().tm_yday

    def _in_window(iso_date):
        try:
            d = datetime.date.fromisoformat(iso_date)
        except ValueError:
            return False
        dy = d.timetuple().tm_yday
        delta = abs(dy - target_yday)
        return min(delta, 365 - delta) <= WINDOW_DAYS

    tmax_vals, tmin_vals, precip_vals = [], [], []
    for i, t in enumerate(times):
        if not _in_window(t):
            continue
        if i < len(tmax) and tmax[i] is not None:
            tmax_vals.append(tmax[i])
        if i < len(tmin) and tmin[i] is not None:
            tmin_vals.append(tmin[i])
        if i < len(precip) and precip[i] is not None:
            precip_vals.append(precip[i])

    def _avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "normal_tmax_f": _avg(tmax_vals),
        "normal_tmin_f": _avg(tmin_vals),
        "normal_daily_precip_in": _avg(precip_vals),
        "years_sampled": end_year - start_year + 1,
        "sample_days": len(tmax_vals),
    }


def _region_meta(region):
    return {
        "name": region["name"], "lat": region["lat"], "lon": region["lon"],
        "futures": region.get("futures"),
        "futures_note": region.get("futures_note"),
        "risk": region["risk"],
    }


async def fetch_region_current(region_key: str):
    """Current conditions + 7-day forecast + vs-normal anomaly for one region."""
    region = REGIONS.get(region_key)
    if not region:
        return {"error": f"unknown region '{region_key}'", "regions": list(REGIONS.keys())}

    cache_key = f"weather:region:{region_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    lat, lon = region["lat"], region["lon"]
    forecast, normal = None, None
    async with aiohttp.ClientSession() as session:
        forecast_task = asyncio.create_task(_fetch_forecast(session, lat, lon))
        normal_task = asyncio.create_task(_fetch_normal(session, lat, lon))
        try:
            forecast = await forecast_task
        except Exception as e:
            logger.warning(f"[Weather] forecast fetch failed for {region_key}: {e}")
        try:
            normal = await normal_task
        except Exception as e:
            logger.warning(f"[Weather] climate-normal fetch failed for {region_key}: {e}")

    if forecast is None:
        return {
            "region_key": region_key, "available": False,
            "reason": "Open-Meteo forecast unavailable", **_region_meta(region),
        }

    current = forecast.get("current") or {}
    daily = forecast.get("daily") or {}
    days   = daily.get("time") or []
    tmax   = daily.get("temperature_2m_max") or []
    tmin   = daily.get("temperature_2m_min") or []
    psum   = daily.get("precipitation_sum") or []
    pprob  = daily.get("precipitation_probability_max") or []

    forecast_days = []
    for i, day in enumerate(days):
        forecast_days.append({
            "date": day,
            "temp_max_f": tmax[i] if i < len(tmax) else None,
            "temp_min_f": tmin[i] if i < len(tmin) else None,
            "precip_in": psum[i] if i < len(psum) else None,
            "precip_prob_pct": pprob[i] if i < len(pprob) else None,
        })

    anomaly = None
    if normal and forecast_days:
        today_row = forecast_days[0]
        today_avg = None
        if today_row["temp_max_f"] is not None and today_row["temp_min_f"] is not None:
            today_avg = (today_row["temp_max_f"] + today_row["temp_min_f"]) / 2
        normal_avg = None
        if normal.get("normal_tmax_f") is not None and normal.get("normal_tmin_f") is not None:
            normal_avg = (normal["normal_tmax_f"] + normal["normal_tmin_f"]) / 2
        temp_anomaly_f = (round(today_avg - normal_avg, 1)
                          if today_avg is not None and normal_avg is not None else None)

        week_precip = sum(d["precip_in"] for d in forecast_days if d["precip_in"] is not None)
        normal_daily_precip = normal.get("normal_daily_precip_in")
        normal_week_precip = round(normal_daily_precip * 7, 2) if normal_daily_precip is not None else None

        anomaly = {
            "temp_vs_normal_f": temp_anomaly_f,
            "precip_7d_actual_in": round(week_precip, 2),
            "precip_7d_normal_in": normal_week_precip,
            "precip_vs_normal_pct": _pct_diff(week_precip, normal_week_precip),
            "years_sampled": normal.get("years_sampled"),
        }

    wcode = current.get("weather_code")
    result = {
        "region_key": region_key,
        "available": True,
        **_region_meta(region),
        "current": {
            "temp_f": current.get("temperature_2m"),
            "precip_in": current.get("precipitation"),
            "wind_mph": current.get("wind_speed_10m"),
            "weather_code": wcode,
            "condition": WEATHER_CODE_DESC.get(wcode, "—"),
            "as_of": current.get("time"),
        },
        "forecast_7d": forecast_days,
        "anomaly": anomaly,
        "timezone": forecast.get("timezone"),
    }
    await cache_set(cache_key, result, ttl=TTL_WEATHER)
    return result


async def fetch_all_regions():
    """Fan out across every region concurrently; degrade gracefully per-region."""
    keys = list(REGIONS.keys())
    results = await asyncio.gather(
        *[fetch_region_current(k) for k in keys],
        return_exceptions=True,
    )
    out = []
    for key, r in zip(keys, results):
        if isinstance(r, Exception):
            out.append({
                "region_key": key, "available": False,
                "reason": str(r)[:150], **_region_meta(REGIONS[key]),
            })
        else:
            out.append(r)
    return {"regions": out, "as_of": datetime.datetime.utcnow().isoformat()}
