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

# ── Redis ───────────────────────────────────────────────────────
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379")

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
