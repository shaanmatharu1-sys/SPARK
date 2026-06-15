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
            max_connections=20,
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
    """Return an async generator yielding messages from a Redis pub/sub channel."""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                yield json.loads(msg["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


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
