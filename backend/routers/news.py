"""
routers/news.py — News feed endpoints
"""
from fastapi import APIRouter, Query
from services.news_client import fetch_news, fetch_ticker_news

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/")
async def get_news(query: str = Query(default=None), refresh: bool = Query(default=False)):
    """GET /news/?query=earnings — Market news feed."""
    return await fetch_news(query=query, force_refresh=refresh)


@router.get("/{symbol}")
async def get_ticker_news(symbol: str):
    """GET /news/AAPL — News for a specific ticker."""
    return await fetch_ticker_news(symbol.upper())
