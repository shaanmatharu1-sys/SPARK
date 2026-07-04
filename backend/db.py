"""
db.py — Async SQLAlchemy engine/session for durable per-user data.

Redis (cache/redis_client.py) stays exactly what it was: an ephemeral,
LRU-evictable cache for market data + pub/sub. This module is the durable
store for accounts and anything framed as "yours" (watchlist, portfolio,
algo configs) — losing that to a cache eviction would read as data loss,
not a cache miss.

DATABASE_URL drives the driver: postgresql+asyncpg://... in production
(Railway managed Postgres addon, same binding pattern as the existing Redis
addon), sqlite+aiosqlite:///... for local dev without a Postgres instance.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
