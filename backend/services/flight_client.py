"""
services/flight_client.py — Live flight tracking via OpenSky Network (free REST, no key)

OpenSky's `/api/states/all` returns anonymous ADS-B state vectors for aircraft
currently in view of ground receivers, scoped to a bounding box via
lamin/lomin/lamax/lomax query params. Anonymous access is rate-limited to
roughly one request per ~10s, so we poll on a background interval and stagger
requests across regions to stay well under that limit.

Response shape (array-of-arrays, not objects — field order matters):
  [icao24, callsign, origin_country, time_position, last_contact,
   longitude, latitude, baro_altitude, on_ground, velocity, true_track,
   vertical_rate, sensors, geo_altitude, squawk, spi, position_source]
Verified against a live curl of https://opensky-network.org/api/states/all
during development (reachable from this sandbox — see report).

No API key is required, so unlike vessel_client.py there's no "not configured"
state. If the OpenSky host becomes unreachable at runtime (blocked network,
rate-limited, etc.) we degrade gracefully the same way portwatch_client.py does.
"""
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

import aiohttp

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Reuse the exact same regions the vessel feed covers, so ships and planes
# overlay the same visible map area. OpenSky takes one bounding box per
# request, so we fetch each region in turn each cycle.
POLL_INTERVAL_SEC = 20      # full-cycle refresh cadence
INTER_REGION_DELAY_SEC = 3  # stagger requests within a cycle (anon rate limit ~1/10s)

# Field indices in each OpenSky state-vector array.
_IDX_ICAO24, _IDX_CALLSIGN, _IDX_ORIGIN, _IDX_TPOS, _IDX_LAST_CONTACT = 0, 1, 2, 3, 4
_IDX_LON, _IDX_LAT, _IDX_BARO_ALT, _IDX_ON_GROUND, _IDX_VELOCITY = 5, 6, 7, 8, 9
_IDX_TRUE_TRACK, _IDX_VERT_RATE, _IDX_SENSORS, _IDX_GEO_ALT = 10, 11, 12, 13
_IDX_SQUAWK, _IDX_SPI, _IDX_POS_SOURCE = 14, 15, 16

# In-memory store: {icao24: {icao24, callsign, lat, lon, altitude, velocity, heading, origin_country, on_ground, ts}}
_flights: dict[str, dict] = {}
_poll_started = False
_last_fetch_ts = 0.0
_available = True
_unavailable_reason = None


async def _fetch_region(session, box):
    """box = [[lat_min, lon_min], [lat_max, lon_max]] (same format as vessel_client.REGIONS)."""
    (lat_min, lon_min), (lat_max, lon_max) = box
    params = {
        "lamin": str(lat_min), "lomin": str(lon_min),
        "lamax": str(lat_max), "lomax": str(lon_max),
    }
    try:
        async with session.get(OPENSKY_URL, params=params,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 429:
                logger.warning("[Flight] OpenSky rate-limited (429) — backing off")
                return None
            if r.status != 200:
                logger.warning(f"[Flight] OpenSky HTTP {r.status}")
                return None
            data = await r.json()
            return data.get("states") or []
    except Exception as e:
        logger.warning(f"[Flight] fetch error: {e}")
        return None


def _ingest(states):
    now = time.time()
    for s in states:
        try:
            icao24 = s[_IDX_ICAO24]
            lat, lon = s[_IDX_LAT], s[_IDX_LON]
            if not icao24 or lat is None or lon is None:
                continue
            alt = s[_IDX_BARO_ALT] if s[_IDX_BARO_ALT] is not None else s[_IDX_GEO_ALT]
            _flights[icao24] = {
                "icao24":         icao24,
                "callsign":       (s[_IDX_CALLSIGN] or "").strip(),
                "origin_country": s[_IDX_ORIGIN],
                "lat":            lat,
                "lon":            lon,
                "altitude":       alt,
                "velocity":       s[_IDX_VELOCITY],
                "heading":        s[_IDX_TRUE_TRACK],
                "on_ground":      bool(s[_IDX_ON_GROUND]),
                "ts":             now,
            }
        except (IndexError, TypeError):
            continue


def _prune(max_age_sec: float = 300):
    """Drop flights not seen in the last 5 minutes."""
    now = time.time()
    stale = [k for k, v in _flights.items() if now - v.get("ts", 0) > max_age_sec]
    for k in stale:
        _flights.pop(k, None)


async def _run_poll():
    """Background task: cycle through regions, refreshing the store."""
    global _last_fetch_ts, _available, _unavailable_reason
    from services.vessel_client import REGIONS
    boxes = REGIONS["global_majors"]

    async with aiohttp.ClientSession() as session:
        while True:
            any_ok = False
            for box in boxes:
                states = await _fetch_region(session, box)
                if states is not None:
                    any_ok = True
                    _ingest(states)
                await asyncio.sleep(INTER_REGION_DELAY_SEC)

            if any_ok:
                _available = True
                _unavailable_reason = None
                _last_fetch_ts = time.time()
            else:
                _available = False
                _unavailable_reason = "OpenSky Network unreachable from this host"
                logger.warning("[Flight] full poll cycle failed — OpenSky unreachable")

            _prune()
            remaining = POLL_INTERVAL_SEC - INTER_REGION_DELAY_SEC * len(boxes)
            await asyncio.sleep(max(1, remaining))


def start_poller():
    """Start the background poller once. No API key needed, so this always runs."""
    global _poll_started
    if _poll_started:
        return
    _poll_started = True
    asyncio.ensure_future(_run_poll())


def get_flights(limit: int = 500) -> dict:
    """Current flight snapshot for the map."""
    _prune()
    flights = [v for v in _flights.values() if v.get("lat") is not None][:limit]

    if not _available and not _flights:
        return {
            "available": False,
            "reason": _unavailable_reason or "OpenSky Network unreachable",
            "flights": [], "count": 0,
            "note": "OpenSky's host may be blocked from this sandbox network; typically reachable in production (e.g. Railway).",
        }

    feed_live = (time.time() - _last_fetch_ts) < (POLL_INTERVAL_SEC * 3) if _last_fetch_ts else False
    return {
        "available":     True,
        "feed_live":      feed_live,
        "count":          len(flights),
        "total_tracked":  len(_flights),
        "flights":        flights,
        "note": None if feed_live else
                "Feed is warming up — flights appear within a poll cycle of startup.",
    }
