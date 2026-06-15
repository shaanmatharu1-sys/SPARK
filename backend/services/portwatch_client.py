"""
services/portwatch_client.py — IMF PortWatch maritime trade data

Official IMF data via open ArcGIS REST API (no key required). Complements the
live AISstream vessel map with analytical trend data:
  - Daily_Chokepoints_Data : transit calls + trade volume for 28 major chokepoints
  - Daily_Ports_Data       : port activity for ~2,065 ports

Updated weekly (Tuesdays ~9AM ET) from satellite AIS on ~90k ships, so this is
TREND/analytical data, not a real-time ticker. Sandbox blocks the host; works
from Railway.

API pattern:
  https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/{dataset}/FeatureServer/0/query
  ?where=<clause>&outFields=*&f=json&orderByFields=date
"""
import asyncio
import logging
import datetime

logger = logging.getLogger(__name__)

import aiohttp
from cache.redis_client import cache_get, cache_set

ARCGIS_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services"
CHOKEPOINTS_DS = "Daily_Chokepoints_Data"
PORTS_DS = "Daily_Ports_Data"

# The 28 chokepoints we care most about surfacing (others available via API).
# Names per PortWatch 'portname' field. The map also uses approx lon/lat.
KEY_CHOKEPOINTS = {
    "Suez Canal":            (32.35, 30.0),
    "Panama Canal":          (-79.9, 9.1),
    "Strait of Hormuz":      (56.3, 26.6),
    "Strait of Malacca":     (100.3, 2.5),
    "Bab el-Mandeb Strait":  (43.3, 12.6),
    "Cape of Good Hope":     (18.5, -34.4),
    "Bosporus Strait":       (29.0, 41.1),
    "Strait of Gibraltar":   (-5.6, 36.0),
    "Danish Straits":        (11.0, 55.5),
    "Dover Strait":          (1.4, 51.0),
    "Taiwan Strait":         (120.0, 24.5),
    "Korea Strait":          (129.0, 34.5),
}


async def _arcgis_query(session, dataset, where, out_fields="*",
                        order_by="date", result_count=None):
    params = {
        "where": where,
        "outFields": out_fields,
        "f": "json",
        "outSR": "4326",
    }
    if order_by:
        params["orderByFields"] = order_by
    if result_count:
        params["resultRecordCount"] = str(result_count)
    url = f"{ARCGIS_BASE}/{dataset}/FeatureServer/0/query"
    try:
        async with session.get(url, params=params,
                               timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return [f.get("attributes", {}) for f in data.get("features", [])]
    except Exception as e:
        logger.error(f"[PortWatch] {dataset} query error: {e}")
        return None


def _parse_date(v):
    """ArcGIS returns dates as epoch ms or ISO; normalize to YYYY-MM-DD."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.datetime.utcfromtimestamp(v / 1000).strftime("%Y-%m-%d")
        except Exception:
            return None
    return str(v)[:10]


async def fetch_chokepoint_trends(days=120):
    """
    Recent daily transit counts for key chokepoints, with a vs-baseline comparison.
    Returns per-chokepoint: latest count, 7d avg, % vs prior period, sparkline.
    """
    cache_key = "portwatch:chokepoints"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    # ArcGIS date filter: timestamp >= since
    where = f"date >= DATE '{since}'"

    async with aiohttp.ClientSession() as session:
        rows = await _arcgis_query(session, CHOKEPOINTS_DS, where,
                                   out_fields="portname,date,n_total,portid")
    if not rows:
        return {"available": False,
                "reason": "PortWatch chokepoint data unavailable (host blocked in sandbox; works on Railway)"}

    # Group by chokepoint
    series = {}
    for r in rows:
        name = r.get("portname")
        d = _parse_date(r.get("date"))
        n = r.get("n_total")
        if not name or d is None or n is None:
            continue
        series.setdefault(name, []).append((d, n))

    out = []
    for name, pts in series.items():
        pts.sort(key=lambda x: x[0])
        counts = [p[1] for p in pts]
        if len(counts) < 8:
            continue
        latest = counts[-1]
        recent7 = sum(counts[-7:]) / 7
        prior7 = sum(counts[-14:-7]) / 7 if len(counts) >= 14 else recent7
        chg = round((recent7 - prior7) / prior7 * 100, 1) if prior7 else None
        out.append({
            "name": name,
            "lonlat": KEY_CHOKEPOINTS.get(name),
            "latest": round(latest, 1),
            "avg_7d": round(recent7, 1),
            "change_7d_pct": chg,
            "spark": counts[-60:],
        })
    # Sort: known key chokepoints first, by activity
    out.sort(key=lambda x: (x["lonlat"] is None, -(x["avg_7d"] or 0)))
    result = {"available": True, "chokepoints": out,
              "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, result, ttl=43200)  # 12h (weekly data)
    return result


async def fetch_port_activity(top_n=40, days=60):
    """
    Recent port activity for major ports — latest port calls + trend.
    Returns top ports by activity with lon/lat for the map.
    """
    cache_key = "portwatch:ports"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    where = f"date >= DATE '{since}'"

    async with aiohttp.ClientSession() as session:
        rows = await _arcgis_query(
            session, PORTS_DS, where,
            out_fields="portname,date,portcalls,lat,lon,country,ISO3,portid")
    if not rows:
        return {"available": False,
                "reason": "PortWatch port data unavailable (host blocked in sandbox; works on Railway)"}

    ports = {}
    for r in rows:
        name = r.get("portname")
        d = _parse_date(r.get("date"))
        calls = r.get("portcalls")
        if not name or d is None or calls is None:
            continue
        p = ports.setdefault(name, {
            "name": name, "country": r.get("country"),
            "lat": r.get("lat"), "lon": r.get("lon"), "series": [],
        })
        p["series"].append((d, calls))

    out = []
    for name, p in ports.items():
        p["series"].sort(key=lambda x: x[0])
        counts = [c for _, c in p["series"]]
        if not counts:
            continue
        recent7 = sum(counts[-7:]) / min(7, len(counts))
        prior7 = sum(counts[-14:-7]) / 7 if len(counts) >= 14 else recent7
        out.append({
            "name": name, "country": p["country"],
            "lat": p["lat"], "lon": p["lon"],
            "avg_7d": round(recent7, 1),
            "change_7d_pct": round((recent7 - prior7) / prior7 * 100, 1) if prior7 else None,
            "spark": counts[-30:],
        })
    out.sort(key=lambda x: -(x["avg_7d"] or 0))
    result = {"available": True, "ports": out[:top_n],
              "as_of": datetime.datetime.utcnow().isoformat()}
    await cache_set(cache_key, result, ttl=43200)
    return result


async def fetch_portwatch_all():
    chokes, ports = await asyncio.gather(
        fetch_chokepoint_trends(), fetch_port_activity(),
        return_exceptions=True,
    )
    def safe(x, k):
        return x if not isinstance(x, Exception) else {"available": False, k: [], "reason": str(x)[:100]}
    return {"chokepoints": safe(chokes, "chokepoints"), "ports": safe(ports, "ports")}
