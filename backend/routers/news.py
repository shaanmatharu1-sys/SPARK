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


@router.get("/ma")
async def get_ma_news():
    """
    GET /news/ma — Mergers & acquisitions news feed (Bloomberg MA function).
    Thin query filter over the same fetch_news() every other feed uses, not
    a new data source: NewsAPI results (when configured) are actually
    query-filtered; the always-on RSS feeds are merged in unfiltered same
    as every other /news call, so treat this as "M&A-weighted", not a pure
    M&A-only feed.
    """
    return await fetch_news(query="merger OR acquisition OR takeover OR buyout")


@router.get("/{symbol}")
async def get_ticker_news(symbol: str):
    """GET /news/AAPL — News for a specific ticker."""
    return await fetch_ticker_news(symbol.upper())
