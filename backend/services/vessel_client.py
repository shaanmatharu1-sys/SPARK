"""
services/vessel_client.py — Live vessel tracking via AISstream.io (free WebSocket)

Maintains an in-memory store of recent vessel positions, fed by a background
WebSocket connection to AISstream. The REST endpoint serves the current
snapshot to the frontend map.

The API key is read from the environment (AISSTREAM_API_KEY) — never hardcoded.
Protocol: wss://stream.aisstream.io/v0/stream
  subscribe: {"APIKey": ..., "BoundingBoxes": [[[lat,lon],[lat,lon]]], "FilterMessageTypes": ["PositionReport"]}
  receive:   {"MessageType":"PositionReport","Message":{"PositionReport":{"UserID","Latitude","Longitude",...}},"MetaData":{...}}
"""
import os
import json
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

AISSTREAM_KEY = os.getenv("AISSTREAM_API_KEY", "")
AISSTREAM_WS = "wss://stream.aisstream.io/v0/stream"

# Bounding boxes for key shipping regions/chokepoints (readable scope, not the whole globe).
# Format AISstream expects: [[[lat_sw, lon_sw], [lat_ne, lon_ne]], ...]
REGIONS = {
    "global_majors": [
        [[-5.0, -10.0], [55.0, 45.0]],     # Europe / Mediterranean / Suez approach
        [[0.0, 95.0],   [40.0, 130.0]],    # South & East China Sea / Singapore / Malacca
        [[20.0, -130.0],[50.0, -65.0]],    # North America coasts
        [[20.0, 50.0],  [30.0, 60.0]],     # Strait of Hormuz / Persian Gulf
    ],
}

# In-memory store: {mmsi: {lat, lon, name, type, sog, cog, ts}}
_vessels: dict[int, dict] = {}
_feed_started = False
_last_message_ts = 0.0


async def _run_feed():
    """Background task: connect to AISstream and continuously update the store."""
    global _last_message_ts
    if not AISSTREAM_KEY:
        logger.warning("[Vessel] AISSTREAM_API_KEY not set — vessel feed disabled")
        return

    try:
        import websockets
    except ImportError:
        logger.error("[Vessel] websockets package not available")
        return

    subscribe = {
        "APIKey": AISSTREAM_KEY,
        "BoundingBoxes": REGIONS["global_majors"],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    while True:
        try:
            logger.info("[Vessel] Connecting -> AISstream")
            async with websockets.connect(AISSTREAM_WS, ping_interval=20) as ws:
                await ws.send(json.dumps(subscribe))
                logger.info("[Vessel] Subscribed to AISstream feed")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    _last_message_ts = time.time()
                    mtype = msg.get("MessageType")
                    meta = msg.get("MetaData", {}) or {}
                    mmsi = meta.get("MMSI") or meta.get("MMSI_String")

                    if mtype == "PositionReport":
                        pr = msg.get("Message", {}).get("PositionReport", {})
                        uid = pr.get("UserID") or mmsi
                        if uid is None:
                            continue
                        existing = _vessels.get(uid, {})
                        _vessels[uid] = {
                            "mmsi": uid,
                            "lat":  pr.get("Latitude"),
                            "lon":  pr.get("Longitude"),
                            "sog":  pr.get("Sog"),          # speed over ground
                            "cog":  pr.get("Cog"),          # course over ground
                            "heading": pr.get("TrueHeading"),
                            "name": existing.get("name") or meta.get("ShipName", "").strip(),
                            "type": existing.get("type"),
                            "ts":   time.time(),
                        }
                    elif mtype == "ShipStaticData":
                        sd = msg.get("Message", {}).get("ShipStaticData", {})
                        uid = sd.get("UserID") or mmsi
                        if uid is None:
                            continue
                        v = _vessels.setdefault(uid, {"mmsi": uid, "ts": time.time()})
                        v["name"] = (meta.get("ShipName") or sd.get("Name") or v.get("name") or "").strip()
                        v["type"] = sd.get("Type")
                        v["destination"] = (sd.get("Destination") or "").strip()
        except Exception as e:
            logger.warning(f"[Vessel] feed error: {e}; reconnecting in 5s")
            await asyncio.sleep(5)


def start_feed(loop=None):
    """Start the background feed once."""
    global _feed_started
    if _feed_started or not AISSTREAM_KEY:
        return
    _feed_started = True
    asyncio.ensure_future(_run_feed())


def _prune(max_age_sec: float = 600):
    """Drop vessels not seen in a while."""
    now = time.time()
    stale = [k for k, v in _vessels.items() if now - v.get("ts", 0) > max_age_sec]
    for k in stale:
        _vessels.pop(k, None)


def get_vessels(limit: int = 500) -> dict:
    """Current vessel snapshot for the map."""
    _prune()
    if not AISSTREAM_KEY:
        return {"available": False, "reason": "AISSTREAM_API_KEY not configured",
                "vessels": [], "note": "Set AISSTREAM_API_KEY in the environment to enable the live vessel feed."}

    vessels = [v for v in _vessels.values() if v.get("lat") is not None][:limit]
    feed_live = (time.time() - _last_message_ts) < 60 if _last_message_ts else False
    return {
        "available":  True,
        "feed_live":  feed_live,
        "count":      len(vessels),
        "total_tracked": len(_vessels),
        "vessels":    vessels,
        "note": None if feed_live else
                "Feed is warming up — vessels appear within a minute of startup.",
    }
