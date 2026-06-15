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
            max_connections=50,
            socket_timeout=30,             # don't block forever on a read
            socket_connect_timeout=10,
            socket_keepalive=True,         # detect dead connections
            health_check_interval=30,      # periodically validate pooled connections
            retry_on_timeout=True,
        )
    return _pool


# ── Helpers ─────────────────────────────────────────────────────

async def cache_set(key: str, value: dict | list, ttl: int = 60):
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> dict | list | None:
    r = await get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str):
    r = await get_redis()
    await r.delete(key)


async def publish(channel: str, message: dict):
    r = await get_redis()
    await r.publish(channel, json.dumps(message))


async def subscribe(channel: str):
    """
    Async generator yielding messages from a Redis pub/sub channel.
    Uses get_message with a timeout (rather than the indefinitely-blocking
    listen()) so a slow/dead Redis read can't hang the connection forever,
    and so client disconnects tear down cleanly without leaking connections.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
            except (asyncio.TimeoutError, ConnectionError):
                # transient: yield nothing, loop continues (keeps WS alive)
                await asyncio.sleep(0.5)
                continue
            if msg and msg.get("type") == "message":
                try:
                    yield json.loads(msg["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
            else:
                # no message this cycle; yield control
                await asyncio.sleep(0.05)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            # redis>=5 uses aclose(); older uses close()
            closer = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
            if closer:
                await closer()
        except Exception:
            pass


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
