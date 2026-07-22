"""
services/flight_client.py — Live flight tracking via adsb.lol (free, no key,
no meaningful rate limit) with airplanes.live as a fallback if adsb.lol is
ever unreachable. Both mirror the same community ADS-B aggregator format.

We previously used OpenSky's anonymous REST API, but anonymous access there
is rate-limited to roughly one request per ~10s *per IP for the whole
network*, and in practice returns 429 almost immediately (verified directly:
a single unauthenticated /states/all call returned 429 on the first try —
that's the root cause the old flight feed rarely showed any planes).
adsb.lol/airplanes.live are point+radius queries (lat, lon, radius_nm —
radius capped at 250nm per call) with no such limit, so instead of a
handful of huge bounding boxes we poll a spread of high-traffic hub points
and merge the results.

Response shape: {"ac": [ {hex, flight, r, t, alt_baro, alt_geom, gs, track,
lat, lon, ...}, ... ]}. alt_baro is either a number (feet) or the literal
string "ground" when the aircraft is on the ground.
"""
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

import aiohttp

PRIMARY_URL  = "https://api.adsb.lol/v2/point"
FALLBACK_URL = "https://api.airplanes.live/v2/point"
RADIUS_NM = 250  # max radius per point query on both APIs

# High-traffic hub points spread across major air-traffic corridors, so the
# 250nm-radius circles cover a broad, globally-representative sample instead
# of just one region.
HUB_POINTS = [
    (40.7, -74.0),    # New York / US Northeast corridor
    (34.0, -118.2),   # Los Angeles / US West Coast
    (41.9, -87.6),    # Chicago / US Midwest hub
    (51.5, -0.1),     # London / Western Europe
    (50.0, 8.6),      # Frankfurt / Central Europe
    (25.3, 55.3),     # Dubai / Middle East hub
    (1.35, 103.8),    # Singapore / SE Asia
    (35.7, 139.7),    # Tokyo / NE Asia
    (22.3, 114.2),    # Hong Kong / South China
    (-33.9, 151.2),   # Sydney / Oceania
]

POLL_INTERVAL_SEC = 20      # full-cycle refresh cadence
INTER_POINT_DELAY_SEC = 1   # light stagger; neither API enforces a hard per-IP limit like OpenSky did

# In-memory store: {hex: {icao24, callsign, lat, lon, altitude, velocity, heading, origin_country, on_ground, ts}}
_flights: dict[str, dict] = {}
_poll_started = False
_last_fetch_ts = 0.0
_available = True
_unavailable_reason = None
_using_fallback = False


async def _fetch_point(session, base_url, lat, lon):
    url = f"{base_url}/{lat}/{lon}/{RADIUS_NM}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                logger.warning(f"[Flight] {base_url} HTTP {r.status}")
                return None
            data = await r.json()
            return data.get("ac") or []
    except Exception as e:
        logger.warning(f"[Flight] fetch error ({base_url}): {e}")
        return None


def _ingest(aircraft):
    now = time.time()
    for a in aircraft:
        try:
            hexid = a.get("hex")
            lat, lon = a.get("lat"), a.get("lon")
            if not hexid or lat is None or lon is None:
                continue
            alt_baro = a.get("alt_baro")
            on_ground = alt_baro == "ground"
            alt = 0 if on_ground else (alt_baro if isinstance(alt_baro, (int, float)) else a.get("alt_geom"))
            _flights[hexid] = {
                "icao24":         hexid,
                "callsign":       (a.get("flight") or "").strip(),
                "origin_country": a.get("ownOp") or a.get("t") or "",
                "lat":            lat,
                "lon":            lon,
                "altitude":       alt,
                "velocity":       a.get("gs"),
                "heading":        a.get("track"),
                "on_ground":      on_ground,
                "ts":             now,
            }
        except (TypeError, ValueError):
            continue


def _prune(max_age_sec: float = 300):
    """Drop flights not seen in the last 5 minutes."""
    now = time.time()
    stale = [k for k, v in _flights.items() if now - v.get("ts", 0) > max_age_sec]
    for k in stale:
        _flights.pop(k, None)


async def _run_poll():
    """Background task: cycle through hub points, refreshing the store."""
    global _last_fetch_ts, _available, _unavailable_reason, _using_fallback

    async with aiohttp.ClientSession() as session:
        while True:
            base_url = FALLBACK_URL if _using_fallback else PRIMARY_URL
            any_ok = False

            for lat, lon in HUB_POINTS:
                aircraft = await _fetch_point(session, base_url, lat, lon)
                if aircraft is not None:
                    any_ok = True
                    _ingest(aircraft)
                await asyncio.sleep(INTER_POINT_DELAY_SEC)

            if any_ok:
                _available = True
                _unavailable_reason = None
                _last_fetch_ts = time.time()
            elif not _using_fallback:
                # Primary failed the whole cycle — flip to the fallback for next time.
                logger.warning("[Flight] adsb.lol unreachable for a full cycle — switching to airplanes.live")
                _using_fallback = True
            else:
                _available = False
                _unavailable_reason = "adsb.lol and airplanes.live both unreachable from this host"
                logger.warning("[Flight] full poll cycle failed on both providers")

            _prune()
            remaining = POLL_INTERVAL_SEC - INTER_POINT_DELAY_SEC * len(HUB_POINTS)
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
            "reason": _unavailable_reason or "flight data providers unreachable",
            "flights": [], "count": 0,
            "note": None,
        }

    feed_live = (time.time() - _last_fetch_ts) < (POLL_INTERVAL_SEC * 3) if _last_fetch_ts else False
    return {
        "available":     True,
        "feed_live":      feed_live,
        "count":          len(flights),
        "total_tracked":  len(_flights),
        "flights":        flights,
        "source":         "airplanes.live" if _using_fallback else "adsb.lol",
        "note": None if feed_live else
                "Feed is warming up — flights appear within a poll cycle of startup.",
    }
