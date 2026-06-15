# ◈ Bloomberg Terminal

Real-time market terminal — FastAPI + React + C++ Greeks engine.

---

## Stack

| Layer         | Tech                                      |
|---------------|-------------------------------------------|
| Frontend      | React 18 + Vite + TradingView Charts      |
| Backend       | FastAPI + WebSockets + APScheduler        |
| Cache/Bus     | Redis (pub/sub + quote cache)             |
| Greeks Engine | C++ (Black-Scholes) via pybind11          |
| Market Data   | Polygon.io (quotes, options, unusual)     |
| Macro Data    | FRED API                                  |
| Sentiment     | CNN Fear & Greed (scraped)               |
| News          | NewsAPI + RSS feeds                       |

---

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Fill in: POLYGON_API_KEY, FRED_API_KEY, NEWS_API_KEY
```

### 2. Start Redis

```bash
docker-compose up redis -d
# OR: brew install redis && redis-server
```

### 3. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Build the C++ Greeks extension
python setup.py build_ext --inplace

# Run
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

---

## Build Phases Status

- [x] **Phase 1** — FastAPI core, Redis, Polygon WS, REST fallbacks
- [x] **Phase 2** — C++ Greeks (Black-Scholes, IV, IV Surface via pybind11)
- [x] **Phase 3** — Macro (FRED), Yield Curve, Fear & Greed, Sectors
- [x] **Phase 4** — News (NewsAPI + RSS), Unusual Activity, Options Flow
- [x] **Frontend** — All panels: Market Monitor, Chart, Options, Macro, Yield Curve,
                      Fear & Greed, Sector Heatmap, News Feed, Unusual Activity

---

## API Reference

```
GET  /health                          Backend + Redis status
GET  /quotes/snapshot?symbols=...     Batch quote snapshots
GET  /quotes/{symbol}                 Single quote
GET  /quotes/{symbol}/bars            OHLCV for charting
WS   /quotes/ws?symbols=...           Real-time trade stream

GET  /options/{symbol}/chain          Options chain
GET  /options/{symbol}/snapshot       Chain + Greeks
WS   /options/ws                      Real-time options quotes

GET  /macro/dashboard                 All FRED indicators
GET  /macro/yield-curve               Full curve + 2s10s spread
GET  /macro/series/{id}               Single FRED series
GET  /macro/series/{id}/history       Multi-year history

GET  /sectors/                        Sector ETF heatmap data
GET  /sentiment/fear-greed            CNN Fear & Greed
GET  /sentiment/supply-chain          Supply chain proxies
GET  /news/                           Market news feed
GET  /news/{symbol}                   Ticker-specific news
GET  /unusual/                        Unusual options activity
WS   /unusual/ws                      Real-time unusual alerts
```

---

## C++ Greeks Extension

After `python setup.py build_ext --inplace`:

```python
from cpp_ext.greeks import greeks_module

g = greeks_module.compute_greeks(S=420.0, K=425.0, T=0.1, r=0.05, sigma=0.25, is_call=True)
print(g.delta, g.gamma, g.vega, g.theta, g.rho)

iv = greeks_module.implied_volatility(market_price=3.50, S=420.0, K=425.0, T=0.1, r=0.05, is_call=True)
print(iv)  # e.g. 0.2487

surface = greeks_module.iv_surface(
    market_prices=[[3.5, 2.1, 1.0], [5.0, 3.2, 1.8]],
    S=420.0,
    strikes=[415.0, 420.0, 425.0],
    expirations=[0.1, 0.25],
    r=0.05,
    is_call=True,
)
```

---

## Polygon Tier Requirements

| Feature                    | Min Tier     |
|----------------------------|--------------|
| Real-time WebSocket quotes | Starter+     |
| Options chain REST         | Developer+   |
| Options WebSocket feed     | Options Add-on|
| Unusual activity endpoint  | Options Add-on|
