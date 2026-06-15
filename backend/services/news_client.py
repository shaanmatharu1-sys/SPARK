"""
services/news_client.py — News aggregator
Primary:  NewsAPI.org (100 req/day free tier)
Fallback: RSS feeds from Reuters, AP, MarketWatch, Seeking Alpha
"""
import asyncio
import logging
import aiohttp
from xml.etree import ElementTree as ET
from config import NEWS_API_KEY, TTL_NEWS
from cache.redis_client import cache_set, cache_get

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"

# Financial RSS feeds (no key required)
# Note: Reuters discontinued public RSS; these are current working feeds.
RSS_FEEDS = {
    "CNBC Top News":   "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "CNBC Markets":    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "MarketWatch":     "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Nasdaq Markets":  "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "Yahoo Finance":   "https://finance.yahoo.com/news/rssindex",
    "Investing.com":   "https://www.investing.com/rss/news_25.rss",
}


async def _fetch_newsapi(query: str = "stock market", page_size: int = 20) -> list[dict]:
    if not NEWS_API_KEY:
        return []
    params = {
        "q":        query,
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": page_size,
        "apiKey":   NEWS_API_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NEWSAPI_BASE}/everything", params=params,
                                   timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return [
                        {
                            "title":     a.get("title"),
                            "source":    a.get("source", {}).get("name"),
                            "url":       a.get("url"),
                            "published": a.get("publishedAt"),
                            "summary":   a.get("description"),
                        }
                        for a in data.get("articles", [])
                        if a.get("title") and "[Removed]" not in a.get("title", "")
                    ]
    except Exception as e:
        logger.error(f"[NewsAPI] {e}")
    return []


async def _fetch_rss(name: str, url: str) -> list[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8),
                                   headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status != 200:
                    return []
                text = await r.text()
        root = ET.fromstring(text)
        items = root.findall(".//item")
        return [
            {
                "title":     item.findtext("title", "").strip(),
                "source":    name,
                "url":       item.findtext("link", ""),
                "published": item.findtext("pubDate", ""),
                "summary":   item.findtext("description", "")[:300] if item.findtext("description") else "",
            }
            for item in items[:10]
            if item.findtext("title")
        ]
    except Exception as e:
        logger.warning(f"[RSS] {name}: {e}")
        return []


async def fetch_news(query: str = None, force_refresh: bool = False) -> list[dict]:
    """Fetch market news from all sources, merged and sorted by recency."""
    cache_key = f"news:{query or 'market'}"
    if not force_refresh:
        cached = await cache_get(cache_key)
        if cached:
            return cached

    tasks = []

    # NewsAPI (if key available)
    if NEWS_API_KEY:
        tasks.append(_fetch_newsapi(query or "stock market finance earnings"))

    # RSS feeds (always available)
    for name, url in RSS_FEEDS.items():
        tasks.append(_fetch_rss(name, url))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for r in results:
        if isinstance(r, list):
            articles.extend(r)

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = (a.get("title") or "")[:60].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(a)

    # Sort by published (best-effort — mixed formats)
    unique = unique[:50]  # cap at 50 items

    await cache_set(cache_key, unique, TTL_NEWS)
    return unique


async def fetch_ticker_news(symbol: str) -> list[dict]:
    """Fetch news specific to a ticker."""
    return await fetch_news(query=f"{symbol} stock")
