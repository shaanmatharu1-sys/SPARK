"""
config.py — Central configuration loaded from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Look for .env in backend/ first, then the project root (one level up).
_here = Path(__file__).resolve().parent
for _candidate in (_here / ".env", _here.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break
else:
    load_dotenv()  # fall back to default search

# ── API Keys ────────────────────────────────────────────────────
POLYGON_API_KEY  = os.getenv("POLYGON_API_KEY", "")
FRED_API_KEY     = os.getenv("FRED_API_KEY", "")
NEWS_API_KEY     = os.getenv("NEWS_API_KEY", "")
EODHD_API_KEY    = os.getenv("EODHD_API_KEY", "")

# ── Webull OpenAPI (crypto market data — stopgap until a dedicated vendor) ──
WEBULL_APP_KEY    = os.getenv("WEBULL_APP_KEY", "")
WEBULL_APP_SECRET = os.getenv("WEBULL_APP_SECRET", "")
WEBULL_REGION     = os.getenv("WEBULL_REGION", "us")

# ── Redis ───────────────────────────────────────────────────────
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── Database (durable per-user data — accounts, watchlists, portfolios) ──
# Railway (and Heroku-style) Postgres plugins inject a plain "postgresql://"
# or "postgres://" URL, but create_async_engine() needs an async driver —
# without it, SQLAlchemy defaults to psycopg2 (sync, not installed) and
# crashes with ModuleNotFoundError. Force the asyncpg driver here.
DATABASE_URL     = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# ── Auth ────────────────────────────────────────────────────────
JWT_SECRET          = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM       = "HS256"
JWT_EXPIRE_DAYS      = 30
SIGNUP_INVITE_CODE  = os.getenv("SIGNUP_INVITE_CODE", "")

# ── App ─────────────────────────────────────────────────────────
ENV              = os.getenv("ENV", "development")
CORS_ORIGINS     = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# ── Market universe ─────────────────────────────────────────────
DEFAULT_WATCHLIST = os.getenv(
    "DEFAULT_WATCHLIST",
    "SPY,QQQ,IWM,AAPL,MSFT,NVDA,TSLA,META,GOOGL,AMZN"
).split(",")

SECTOR_ETFS = os.getenv(
    "SECTOR_ETFS",
    "XLF,XLE,XLK,XLV,XLI,XLB,XLU,XLRE,XLC,XLP,XLY"
).split(",")

# ── Polygon WS endpoints ────────────────────────────────────────
POLYGON_WS_STOCKS  = "wss://socket.polygon.io/stocks"
POLYGON_WS_OPTIONS = "wss://socket.polygon.io/options"

# ── FRED macro series ───────────────────────────────────────────
FRED_SERIES = {
    # Yield curve (full)
    "DGS1MO": "1M", "DGS3MO": "3M", "DGS6MO": "6M",
    "DGS1":   "1Y", "DGS2":   "2Y", "DGS3":   "3Y",
    "DGS5":   "5Y", "DGS7":   "7Y", "DGS10":  "10Y",
    "DGS20":  "20Y","DGS30":  "30Y",
    # Macro indicators
    "CPIAUCSL":  "CPI",
    "UNRATE":    "Unemployment",
    "FEDFUNDS":  "Fed Funds Rate",
    "T10YIE":    "10Y Breakeven Inflation",
    "VIXCLS":    "VIX",
    "DCOILWTICO":"WTI Crude Oil",
    "DEXUSEU":   "EUR/USD",
    "DEXJPUS":   "USD/JPY",
    "GDP":       "GDP",
    "M2SL":      "M2 Money Supply",
}

# ── Cache TTLs (seconds) ────────────────────────────────────────
TTL_QUOTE    = 2
TTL_OPTIONS  = 5
TTL_MACRO    = 3600          # 1hr — FRED doesn't update intraday
TTL_NEWS     = 300           # 5min
TTL_FG       = 600           # 10min
TTL_SECTORS  = 30
TTL_UNUSUAL  = 60
TTL_FUTURES  = 60            # yfinance quotes — futures move faster than intl indices
TTL_COT      = 259200        # 3 days — CFTC COT report only updates weekly (Fridays)
TTL_WEATHER  = 1800           # 30min — forecasts don't need to be near-real-time
TTL_ORDERBOOK = 5             # REST fallback only — the live book is pushed over WS
TTL_FX       = 1800           # 30min — Frankfurter/ECB rates only update once/day anyway
TTL_CRYPTO_WEBULL   = 20     # crypto snapshot — Webull free tier is 1 req/sec per App Key
TTL_CRYPTO_INSTRUMENTS = 21600  # 6hr — the list of tradable crypto symbols barely changes

# ── WebSocket reliability ────────────────────────────────────────
# After this many consecutive connect/auth/subscribe failures, stop the fast
# exponential backoff and cool down for WS_CIRCUIT_BREAKER_COOLDOWN seconds
# instead — protects against hammering Polygon's endpoint indefinitely if
# something is structurally broken (bad entitlement, bad credentials, etc).
WS_CIRCUIT_BREAKER_THRESHOLD = 3
WS_CIRCUIT_BREAKER_COOLDOWN  = 600   # 10 min
WS_RECV_TIMEOUT              = 25    # seconds without any message before treating the connection as stalled
