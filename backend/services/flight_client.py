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
RADIUS_NM = 250  # hard max per point query on both APIs — a larger value doesn't
                 # get you more coverage, it just hangs: verified directly,
                 # radius=250 returns in ~7s, radius=100000 didn't return in 120s.

# High-traffic hub points spread across major air-traffic corridors. 10 points
# at 250nm radius only covers well under 1% of Earth's surface, which is why
# the feed looked sparse even when it was working — widened to ~30 points
# across every populated continent for meaningfully denser real coverage.
# Fetched in parallel (see _run_poll), so more points costs latency, not a
# slower refresh cycle.
HUB_POINTS = [
    # North America
    (40.7, -74.0),    # New York
    (34.0, -118.2),   # Los Angeles
    (41.9, -87.6),    # Chicago
    (25.8, -80.2),    # Miami
    (32.9, -97.0),    # Dallas-Fort Worth
    (47.6, -122.3),   # Seattle
    (43.7, -79.4),    # Toronto
    (19.4, -99.1),    # Mexico City
    # South America
    (-23.6, -46.6),   # São Paulo
    (-34.6, -58.4),   # Buenos Aires
    (4.7, -74.1),     # Bogotá
    # Europe
    (51.5, -0.1),     # London
    (50.0, 8.6),      # Frankfurt
    (48.9, 2.4),      # Paris
    (40.4, -3.7),     # Madrid
    (41.9, 12.5),     # Rome
    (52.2, 21.0),     # Warsaw
    (55.8, 37.6),     # Moscow
    # Middle East
    (25.3, 55.3),     # Dubai
    (25.3, 51.5),     # Doha
    (41.0, 29.0),     # Istanbul
    # Africa
    (-26.1, 28.0),    # Johannesburg
    (30.1, 31.4),     # Cairo
    (6.6, 3.3),       # Lagos
    (-1.3, 36.8),     # Nairobi
    # Asia
    (1.35, 103.8),    # Singapore
    (35.7, 139.7),    # Tokyo
    (22.3, 114.2),    # Hong Kong
    (31.2, 121.5),    # Shanghai
    (19.1, 72.9),     # Mumbai
    (28.6, 77.2),     # Delhi
    (13.7, 100.5),    # Bangkok
    (37.6, 127.0),    # Seoul
    # Oceania
    (-33.9, 151.2),   # Sydney
    (-36.8, 174.8),   # Auckland
]

POLL_INTERVAL_SEC = 20      # full-cycle refresh cadence (measured from cycle start)

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


MAX_CONCURRENT_REQUESTS = 4  # firing all ~30 points at once trips adsb.lol's
                             # concurrency limit (verified: got 429s back
                             # instantly on several points under full parallelism)


async def _fetch_point_limited(session, base_url, lat, lon, sem):
    async with sem:
        return await _fetch_point(session, base_url, lat, lon)


async def _run_poll():
    """Background task: fetch hub points (bounded concurrency) each cycle, refreshing the store."""
    global _last_fetch_ts, _available, _unavailable_reason, _using_fallback

    async with aiohttp.ClientSession() as session:
        while True:
            cycle_start = time.time()
            base_url = FALLBACK_URL if _using_fallback else PRIMARY_URL

            # Bounded concurrency, not full parallelism: sequential fetching
            # (the original version) made each real-world request (~7s
            # observed) add up across 30 points into minutes per cycle, but
            # firing all 30 at once trips adsb.lol's per-IP concurrency
            # limit (429s). A small semaphore gets most of the speed
            # without the rate-limit hit.
            sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
            results = await asyncio.gather(
                *[_fetch_point_limited(session, base_url, lat, lon, sem) for lat, lon in HUB_POINTS]
            )
            any_ok = False
            for aircraft in results:
                if aircraft is not None:
                    any_ok = True
                    _ingest(aircraft)

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
            elapsed = time.time() - cycle_start
            await asyncio.sleep(max(1, POLL_INTERVAL_SEC - elapsed))


def start_poller():
    """Start the background poller once. No API key needed, so this always runs."""
    global _poll_started
    if _poll_started:
        return
    _poll_started = True
    asyncio.ensure_future(_run_poll())


def get_flights(limit: int = 3000) -> dict:
    """
    Current flight snapshot for the map. Default limit raised from 500 to
    3000 (30 hub points now regularly track 2000+ concurrent aircraft) —
    500 wasn't a deliberate cap, and since _flights is a plain insertion-
    ordered dict, truncating at a low limit meant only whichever hub was
    fetched/ingested first ever made it onscreen, making global coverage
    look far sparser than what's actually tracked.
    """
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
