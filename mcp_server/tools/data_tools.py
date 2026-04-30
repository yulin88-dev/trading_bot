"""MCP tools for data fetching.

Each tool tries the primary vendor first, falls back to yfinance on failure,
and returns a structured error dict if all sources fail. Tools never raise —
they always return a dict the caller can render.
"""
from __future__ import annotations

import logging

from mcp_server.config import normalize_symbol
from mcp_server.data import alpaca_client, coingecko_client, yfinance_client

log = logging.getLogger(__name__)


def get_price_history(symbol: str, days: int = 30) -> dict:
    """Get OHLCV daily price history for a symbol.

    Args:
        symbol: Asset ticker (TSLA, BRK-B, BTC, SPY).
        days: Number of trading/calendar days to fetch.

    Returns:
        Dict with `symbol`, `source`, and `bars` (list of OHLCV bars), or
        `{"error": "...", "symbol": "..."}` if all sources fail.
    """
    try:
        sym = normalize_symbol(symbol)
    except ValueError as e:
        return _error(str(e), symbol=symbol)

    if sym["alpaca"]:
        return _try_then_fallback(
            primary_name="alpaca",
            primary_fn=lambda: alpaca_client.get_bars(sym["alpaca"], days),
            fallback_fn=lambda: yfinance_client.get_bars(sym["yfinance"], days),
            display=sym["display"],
            payload_key="bars",
        )
    if sym["coingecko"]:
        return _try_then_fallback(
            primary_name="coingecko",
            primary_fn=lambda: coingecko_client.get_bars(sym["coingecko"], days),
            fallback_fn=lambda: yfinance_client.get_bars(sym["yfinance"], days),
            display=sym["display"],
            payload_key="bars",
        )
    return _error("No data source mapping for symbol", symbol=symbol)


def get_current_quote(symbol: str) -> dict:
    """Get the latest snapshot quote for a symbol.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with `symbol`, `source`, `price`, `change_pct`, `volume`, `as_of`,
        or `{"error": "...", "symbol": "..."}`.
    """
    try:
        sym = normalize_symbol(symbol)
    except ValueError as e:
        return _error(str(e), symbol=symbol)

    if sym["alpaca"]:
        return _try_then_fallback_flat(
            primary_name="alpaca",
            primary_fn=lambda: alpaca_client.get_snapshot(sym["alpaca"]),
            fallback_fn=lambda: yfinance_client.get_snapshot(sym["yfinance"]),
            display=sym["display"],
        )
    if sym["coingecko"]:
        return _try_then_fallback_flat(
            primary_name="coingecko",
            primary_fn=lambda: coingecko_client.get_simple_price(sym["coingecko"]),
            fallback_fn=lambda: yfinance_client.get_snapshot(sym["yfinance"]),
            display=sym["display"],
        )
    return _error("No data source mapping for symbol", symbol=symbol)


def get_news(symbol: str, days: int = 7) -> dict:
    """Get recent news headlines for a symbol.

    Stocks use Alpaca's news API. BTC news is skipped in v1 and returns an
    empty items list.

    Args:
        symbol: Asset ticker.
        days: Look-back window in days.

    Returns:
        Dict with `symbol`, `source`, and `items` (list of news entries), or
        `{"error": "...", "symbol": "..."}` if the source fails.
    """
    try:
        sym = normalize_symbol(symbol)
    except ValueError as e:
        return _error(str(e), symbol=symbol)

    if sym["alpaca"]:
        try:
            items = alpaca_client.get_news(sym["alpaca"], days)
            return {"symbol": sym["display"], "source": "alpaca", "items": items}
        except Exception as e:
            log.warning("Alpaca news failed for %s: %s", sym["display"], e)
            return _error(f"Alpaca news error: {e}", symbol=sym["display"], items=[])
    if sym["coingecko"]:
        return {"symbol": sym["display"], "source": "v1-skip", "items": []}
    return _error("No news source mapping for symbol", symbol=symbol)


def _try_then_fallback(
    *,
    primary_name: str,
    primary_fn,
    fallback_fn,
    display: str,
    payload_key: str,
) -> dict:
    try:
        payload = primary_fn()
        return {"symbol": display, "source": primary_name, payload_key: payload}
    except Exception as e:
        log.warning("%s failed for %s: %s", primary_name, display, e)
        try:
            payload = fallback_fn()
            return {"symbol": display, "source": "yfinance", payload_key: payload}
        except Exception as e2:
            return _error(
                f"{primary_name} failed ({e}); yfinance fallback failed ({e2})",
                symbol=display,
            )


def _try_then_fallback_flat(
    *,
    primary_name: str,
    primary_fn,
    fallback_fn,
    display: str,
) -> dict:
    try:
        payload = primary_fn()
        return {"symbol": display, "source": primary_name, **payload}
    except Exception as e:
        log.warning("%s snapshot failed for %s: %s", primary_name, display, e)
        try:
            payload = fallback_fn()
            return {"symbol": display, "source": "yfinance", **payload}
        except Exception as e2:
            return _error(
                f"{primary_name} failed ({e}); yfinance fallback failed ({e2})",
                symbol=display,
            )


def _error(msg: str, **extra) -> dict:
    return {"error": msg, **extra}
