"""Alpaca client wrapper: stock bars, snapshot quotes, news.

Uses paper-trading credentials from env. Symbols are passed in Alpaca's
expected form (e.g. "BRKB"); the caller is responsible for normalization.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpaca.data.enums import DataFeed
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import (
    NewsRequest,
    StockBarsRequest,
    StockSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame

from mcp_server.config import ALPACA_API_KEY, ALPACA_SECRET_KEY


def _require_creds() -> None:
    if not (ALPACA_API_KEY and ALPACA_SECRET_KEY):
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in the environment."
        )


def _bars_client() -> StockHistoricalDataClient:
    _require_creds()
    return StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


def _news_client() -> NewsClient:
    _require_creds()
    return NewsClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


def get_bars(symbol: str, days: int) -> list[dict]:
    """Daily OHLCV bars over the past `days` calendar days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days * 2 + 5)  # buffer for weekends/holidays

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment="all",
        feed=DataFeed.IEX,
    )
    response = _bars_client().get_stock_bars(request)
    rows = response.data.get(symbol, [])
    bars = [
        {
            "date": b.timestamp.date().isoformat(),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in rows
    ]
    return bars[-days:]


def get_snapshot(symbol: str) -> dict:
    """Latest snapshot quote — price, daily % change, volume."""
    request = StockSnapshotRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    snapshot = _bars_client().get_stock_snapshot(request)
    s = snapshot[symbol]

    latest_trade = s.latest_trade
    daily_bar = s.daily_bar
    prev_bar = s.previous_daily_bar

    price = float(latest_trade.price)
    change_pct = None
    if prev_bar and prev_bar.close:
        change_pct = (price / float(prev_bar.close) - 1.0) * 100.0

    return {
        "price": price,
        "change_pct": change_pct,
        "volume": float(daily_bar.volume) if daily_bar else None,
        "as_of": latest_trade.timestamp.isoformat(),
    }


def get_news(symbol: str, days: int) -> list[dict]:
    """News items for a symbol over the past `days` calendar days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    request = NewsRequest(
        symbols=symbol,
        start=start,
        end=end,
        limit=20,
        include_content=False,
    )
    response = _news_client().get_news(request)
    items = getattr(response, "news", None) or response.data.get("news", [])

    return [
        {
            "date": (
                n.created_at.isoformat()
                if hasattr(n.created_at, "isoformat")
                else str(n.created_at)
            ),
            "title": n.headline,
            "source": getattr(n, "source", "alpaca") or "alpaca",
            "url": n.url or "",
            "summary": n.summary or "",
        }
        for n in items
    ]
