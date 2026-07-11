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
from routers import quotes, options, macro, news, sectors, sentiment, unusual_activity, quant, factors, vol, algo, research, markets, watchlist, traders, research_ext, international, altdata, fundamentals, futures, workspace, alerts, regime, auth as auth_router

# ── Background WS feeds ──────────────────────────────────────────────────────
from services.polygon_client import PolygonStocksWS, PolygonOptionsWS

# ── Scheduled refreshes ──────────────────────────────────────────────────────
from services.fred_client    import fetch_macro_dashboard, fetch_yield_curve
from services.fear_greed     import fetch_fear_greed
from services.news_client    import fetch_news
from services.polygon_client import fetch_snapshot, fetch_unusual_activity
from sqlalchemy import select
from db import AsyncSessionLocal
from models import Alert
from cache.redis_client import publish

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

    # Market regime — precompute hourly (depends on the relationships job's
    # cached universe returns for breadth, so prime it a bit after that job)
    async def _refresh_regime():
        try:
            from analytics.regime.engine import precompute_market_regime
            await precompute_market_regime()
        except Exception as e:
            logger.warning(f"[Regime] precompute failed: {e}")
    scheduler.add_job(_refresh_regime, "interval", hours=1, id="market_regime")
    scheduler.add_job(_refresh_regime, "date",
                      run_date=datetime.datetime.now() + datetime.timedelta(seconds=120),
                      id="market_regime_prime")

    # Price alerts — check active alerts against live prices every 30s
    async def _check_price_alerts():
        async with AsyncSessionLocal() as db:
            rows = (await db.scalars(select(Alert).where(Alert.active == True))).all()
            if not rows:
                return
            symbols = list({r.symbol for r in rows})
            try:
                snap = await fetch_snapshot(symbols)
            except Exception as e:
                logger.warning(f"[Alerts] snapshot fetch failed: {e}")
                return
            for r in rows:
                d = snap.get(r.symbol, {})
                last = ((d.get("lastTrade", {}) or {}).get("p")
                        or (d.get("day", {}) or {}).get("c")
                        or (d.get("prevDay", {}) or {}).get("c"))
                if last is None:
                    continue
                hit = ((r.condition == "above" and last >= r.threshold)
                       or (r.condition == "below" and last <= r.threshold))
                if hit:
                    r.active = False
                    r.triggered_at = datetime.datetime.utcnow()
                    await publish(f"alerts:{r.user_id}", {
                        "type": "alert_triggered", "id": r.id, "symbol": r.symbol,
                        "condition": r.condition, "threshold": r.threshold, "price": last,
                    })
            await db.commit()
    scheduler.add_job(_check_price_alerts, "interval", seconds=30, id="price_alerts")

    scheduler.start()
    logger.info("[Scheduler] Started — macro/1hr, F&G/10min, news/5min, sectors/30s, ties/4hr, alerts/30s")


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

    # Database health check (schema itself is managed by `alembic upgrade head`
    # as a separate deploy step, not created here — see backend/alembic/)
    from sqlalchemy import text
    from db import engine as db_engine
    try:
        async with db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("[DB] Connected")
    except Exception as e:
        logger.warning(f"[DB] Not reachable — auth/per-user data will fail: {e}")

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

    # Start flight-tracking poller (OpenSky Network, no key needed)
    from services import flight_client
    flight_client.start_poller()
    logger.info("[Flight] OpenSky poller starting...")

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
app.include_router(fundamentals.router)
app.include_router(futures.router)
app.include_router(workspace.router)
app.include_router(alerts.router)
app.include_router(regime.router)
app.include_router(auth_router.router)


# ── Health check ──────────────────────────────────────────────────────────────
# feeds.stocks_ws/options_ws used to just report `.running` (a flag that
# stays True for the entire life of a silently-failing reconnect loop, so
# this always reported "healthy" even when no real tick had ever arrived —
# see the root-cause note on _WSFeedBase in services/polygon_client.py).
# Now reports real connection state instead.
@app.get("/health")
async def health():
    redis_ok = await redis_ping()
    return {
        "status": "ok",
        "redis":  redis_ok,
        "feeds": {
            "stocks_ws":  stocks_ws.health(),
            "options_ws": options_ws.health(),
        },
    }


@app.get("/")
async def root():
    return {"message": "Bloomberg Terminal API", "docs": "/docs"}
