"""
cache/redis_client.py — Async Redis wrapper with pub/sub support
"""
import json
import asyncio
import redis.asyncio as aioredis
from config import REDIS_URL

# ── Singleton connection pool ────────────────────────────────────
_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=80,
            socket_timeout=30,             # don't block forever on a read
            socket_connect_timeout=10,
            socket_keepalive=True,         # detect dead connections
            health_check_interval=30,      # periodically validate pooled connections
            retry_on_timeout=True,
        )
    return _pool


# ── Helpers ─────────────────────────────────────────────────────

async def cache_set(key: str, value: dict | list, ttl: int = 60):
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value))
    except Exception:
        # cache write failures must never break the request path
        pass


async def cache_get(key: str) -> dict | list | None:
    try:
        r = await get_redis()
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        # treat any cache read failure as a miss; caller will fetch live data
        return None


async def cache_delete(key: str):
    r = await get_redis()
    await r.delete(key)


async def publish(channel: str, message: dict):
    r = await get_redis()
    await r.publish(channel, json.dumps(message))


# ── Shared pub/sub fan-out ───────────────────────────────────────
# Instead of one Redis pub/sub connection PER WebSocket client (which exhausts
# the connection pool under many clients / reconnect storms), we maintain ONE
# Redis pub/sub connection per channel and fan messages out to all subscribed
# clients via in-process asyncio queues. N clients = 1 Redis connection.

_channel_subscribers: dict[str, set] = {}   # channel -> set[asyncio.Queue]
_channel_listeners: dict[str, asyncio.Task] = {}  # channel -> background task
_channel_lock = asyncio.Lock()


async def _channel_listener(channel: str):
    """Single background task per channel: reads Redis pub/sub, fans out to queues."""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            # stop if no subscribers remain
            if not _channel_subscribers.get(channel):
                break
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            except (asyncio.TimeoutError, ConnectionError):
                await asyncio.sleep(0.5)
                continue
            except Exception:
                await asyncio.sleep(1.0)
                continue
            if msg and msg.get("type") == "message":
                try:
                    data = json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                # fan out to all subscriber queues (non-blocking)
                for q in list(_channel_subscribers.get(channel, [])):
                    try:
                        q.put_nowait(data)
                    except asyncio.QueueFull:
                        pass  # slow client; drop rather than block everyone
            else:
                await asyncio.sleep(0.02)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            closer = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
            if closer:
                await closer()
        except Exception:
            pass
        _channel_listeners.pop(channel, None)


async def subscribe(channel: str):
    """
    Async generator yielding messages for a WS client. Registers an in-process
    queue with the shared channel listener — does NOT open its own Redis
    connection. This keeps Redis usage flat regardless of client count.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    async with _channel_lock:
        _channel_subscribers.setdefault(channel, set()).add(q)
        # start the shared listener for this channel if not already running
        if channel not in _channel_listeners or _channel_listeners[channel].done():
            _channel_listeners[channel] = asyncio.create_task(_channel_listener(channel))
    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # keep the generator alive; lets the WS detect disconnects
                continue
            yield data
    finally:
        async with _channel_lock:
            subs = _channel_subscribers.get(channel)
            if subs:
                subs.discard(q)
                if not subs:
                    _channel_subscribers.pop(channel, None)


async def hset_quote(symbol: str, data: dict):
    """Store a live quote as a Redis hash for O(1) field access."""
    r = await get_redis()
    await r.hset(f"quote:{symbol}", mapping={k: str(v) for k, v in data.items()})
    await r.expire(f"quote:{symbol}", 10)


async def hget_quote(symbol: str) -> dict | None:
    r = await get_redis()
    raw = await r.hgetall(f"quote:{symbol}")
    return raw if raw else None


async def ping() -> bool:
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        return False
