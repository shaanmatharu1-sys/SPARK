"""
main.py — Bloomberg Terminal Backend
FastAPI app with WebSocket support, background data feeds, and scheduler.

Run:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import datetime
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import CORS_ORIGINS, DEFAULT_WATCHLIST, SECTOR_ETFS
from cache.redis_client import ping as redis_ping

# ── Routers ──────────────────────────────────────────────────────────────────
from routers import quotes, options, macro, news, sectors, sentiment, unusual_activity, quant, factors, vol, algo, research, markets, watchlist, traders, research_ext, international, altdata

# ── Background WS feeds ──────────────────────────────────────────────────────
from services.polygon_client import PolygonStocksWS, PolygonOptionsWS

# ── Scheduled refreshes ──────────────────────────────────────────────────────
from services.fred_client    import fetch_macro_dashboard, fetch_yield_curve
from services.fear_greed     import fetch_fear_greed
from services.news_client    import fetch_news
from services.polygon_client import fetch_snapshot, fetch_unusual_activity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── WebSocket feed instances ──────────────────────────────────────────────────
stocks_ws  = PolygonStocksWS(symbols=DEFAULT_WATCHLIST + SECTOR_ETFS)
options_ws = PolygonOptionsWS(symbols=DEFAULT_WATCHLIST)

# ── Scheduler ────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()


def setup_scheduler():
    # Macro / FRED — refresh every hour
    scheduler.add_job(fetch_macro_dashboard, "interval", minutes=60,  id="macro_dashboard")
    scheduler.add_job(fetch_yield_curve,     "interval", minutes=60,  id="yield_curve")

    # Fear & Greed — refresh every 10 min
    scheduler.add_job(fetch_fear_greed,      "interval", minutes=10,  id="fear_greed")

    # News — refresh every 5 min
    scheduler.add_job(fetch_news,            "interval", minutes=5,   id="news")

    # Sector snapshots — refresh every 30s
    async def _refresh_sectors():
        await fetch_snapshot(SECTOR_ETFS)
    scheduler.add_job(_refresh_sectors, "interval", seconds=30, id="sector_snapshot")

    # Unusual activity — refresh every 60s
    scheduler.add_job(fetch_unusual_activity, "interval", seconds=60, id="unusual_activity")

    # Company-relationship matrix — precompute every 4 hours (heavy: ~500 symbols)
    async def _refresh_relationships():
        try:
            from analytics.relationships.engine import precompute_relationships
            await precompute_relationships()
        except Exception as e:
            logger.warning(f"[Relationships] precompute failed: {e}")
    scheduler.add_job(_refresh_relationships, "interval", hours=4, id="relationships")
    # Prime it once shortly after startup so the first user click is warm
    scheduler.add_job(_refresh_relationships, "date",
                      run_date=datetime.datetime.now() + datetime.timedelta(seconds=90),
                      id="relationships_prime")

    scheduler.start()
    logger.info("[Scheduler] Started — macro/1hr, F&G/10min, news/5min, sectors/30s, ties/4hr")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("══════════════════════════════════════════")
    logger.info("  Bloomberg Terminal Backend — Starting")
    logger.info("══════════════════════════════════════════")

    # Redis health check
    if await redis_ping():
        logger.info("[Redis] Connected")
    else:
        logger.warning("[Redis] Not reachable — caching disabled")

    # Warm up caches on startup
    logger.info("[Startup] Pre-warming caches...")
    await asyncio.gather(
        fetch_macro_dashboard(),
        fetch_yield_curve(),
        fetch_fear_greed(),
        fetch_news(),
        fetch_snapshot(DEFAULT_WATCHLIST + SECTOR_ETFS),
        return_exceptions=True,
    )
    logger.info("[Startup] Cache warm-up complete")

    # Start Polygon WebSocket feeds
    asyncio.create_task(stocks_ws.start(),  name="polygon_stocks_ws")
    asyncio.create_task(options_ws.start(), name="polygon_options_ws")
    logger.info("[Polygon] WebSocket feeds starting...")

    # Start vessel-tracking feed (AISstream) if configured
    from services import vessel_client
    vessel_client.start_feed()
    if vessel_client.AISSTREAM_KEY:
        logger.info("[Vessel] AISstream feed starting...")

    # Start scheduler
    setup_scheduler()

    yield  # app is running

    # Shutdown
    logger.info("[Shutdown] Stopping feeds and scheduler...")
    await stocks_ws.stop()
    await options_ws.stop()
    scheduler.shutdown(wait=False)
    logger.info("[Shutdown] Clean exit")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bloomberg Terminal API",
    version="1.0.0",
    description="Real-time market data, options flow, macro analytics",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(quotes.router)
app.include_router(options.router)
app.include_router(macro.router)
app.include_router(news.router)
app.include_router(sectors.router)
app.include_router(sentiment.router)
app.include_router(unusual_activity.router)
app.include_router(quant.router)
app.include_router(factors.router)
app.include_router(vol.router)
app.include_router(algo.router)
app.include_router(research.router)
app.include_router(markets.router)
app.include_router(watchlist.router)
app.include_router(traders.router)
app.include_router(research_ext.router)
app.include_router(international.router)
app.include_router(altdata.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    redis_ok = await redis_ping()
    return {
        "status": "ok",
        "redis":  redis_ok,
        "feeds": {
            "stocks_ws":  stocks_ws.running,
            "options_ws": options_ws.running,
        },
    }


@app.get("/")
async def root():
    return {"message": "Bloomberg Terminal API", "docs": "/docs"}
