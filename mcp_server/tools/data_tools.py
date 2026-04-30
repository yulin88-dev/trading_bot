"""MCP tool stubs for data fetching. Real logic lands in Prompt 3."""
from __future__ import annotations


def get_price_history(symbol: str, days: int = 30) -> dict:
    """Get OHLCV daily price history for a symbol.

    Args:
        symbol: Asset ticker (TSLA, BRK-B, BTC, SPY).
        days: Number of trading days to fetch.

    Returns:
        Dict with bars list — each bar has date, open, high, low, close, volume.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "days": days,
        "bars": [],
    }


def get_current_quote(symbol: str) -> dict:
    """Get the latest snapshot quote for a symbol.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with price, change_pct, volume, as_of.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "price": None,
        "change_pct": None,
        "volume": None,
        "as_of": None,
    }


def get_news(symbol: str, days: int = 7) -> dict:
    """Get recent news headlines for a symbol.

    Stocks use Alpaca's news API. BTC news is skipped in v1 and returns an
    empty items list.

    Args:
        symbol: Asset ticker.
        days: Look-back window in days.

    Returns:
        Dict with items list — each item has date, title, source, url, summary.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "days": days,
        "items": [],
    }
