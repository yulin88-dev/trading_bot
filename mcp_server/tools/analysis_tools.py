"""MCP tools for analysis. Each fetches bars via data_tools, then computes math."""
from __future__ import annotations

import logging

from mcp_server.analysis import benchmark, performance, technicals, volatility
from mcp_server.config import normalize_symbol
from mcp_server.tools.data_tools import get_price_history

log = logging.getLogger(__name__)

# Bars to fetch for each tool. For stocks these are trading days; for BTC
# these are calendar days. In practice yfinance/Alpaca return ~252 trading
# days per year and CoinGecko returns ~365 calendar days, so picking 90+
# is enough for SMA(50) and 30+30 volatility windows on either.
_PERFORMANCE_BARS = 30
_TECHNICALS_BARS = 90
_VOLATILITY_BARS = 90
_BENCHMARK_BARS = 90


def _is_crypto(symbol: str) -> bool:
    return normalize_symbol(symbol)["coingecko"] is not None


def _fetch_bars(symbol: str, days: int) -> list[dict]:
    """Pull bars and unwrap. Raises on error so the wrapper can catch."""
    result = get_price_history(symbol, days=days)
    if "error" in result:
        raise RuntimeError(result["error"])
    bars = result.get("bars", [])
    if not bars:
        raise RuntimeError(f"No bars returned for {symbol}")
    return bars


def compute_weekly_performance(symbol: str) -> dict:
    """Compute past-7d vs prior-7d performance.

    Stocks use a 5-bar trading week; crypto uses a 7-bar calendar week.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with weekly_return_pct, week_high, week_low, avg_volume,
        prior_week_return_pct, delta_pp — or `{"error": ...}`.
    """
    try:
        bars = _fetch_bars(symbol, _PERFORMANCE_BARS)
        window = 7 if _is_crypto(symbol) else 5
        result = performance.compute_weekly_performance(bars, window=window)
        return {"symbol": symbol, **result}
    except Exception as e:
        log.warning("compute_weekly_performance(%s) failed: %s", symbol, e)
        return {"error": str(e), "symbol": symbol}


def compute_technicals(symbol: str) -> dict:
    """Compute RSI(14), SMA(20/50), and MACD(12,26,9) at the latest bar.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with rsi_14, rsi_label, sma_20, sma_50, macd_line, macd_signal,
        macd_hist, price_vs_sma20, price_vs_sma50, crossover_signal — or
        `{"error": ...}`.
    """
    try:
        bars = _fetch_bars(symbol, _TECHNICALS_BARS)
        result = technicals.compute_technicals(bars)
        return {"symbol": symbol, **result}
    except Exception as e:
        log.warning("compute_technicals(%s) failed: %s", symbol, e)
        return {"error": str(e), "symbol": symbol}


def compute_volatility(symbol: str) -> dict:
    """Compute trailing-30 annualized vol vs prior-30 annualized vol.

    Stocks use 252-day annualization; crypto uses 365-day annualization.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with ann_vol_30d, ann_vol_prior_30d, vol_delta_pct — or
        `{"error": ...}`.
    """
    try:
        bars = _fetch_bars(symbol, _VOLATILITY_BARS)
        annualization = 365 if _is_crypto(symbol) else 252
        result = volatility.compute_volatility(bars, annualization=annualization)
        return {"symbol": symbol, **result}
    except Exception as e:
        log.warning("compute_volatility(%s) failed: %s", symbol, e)
        return {"error": str(e), "symbol": symbol}


def compare_to_benchmark(symbol: str, benchmark_symbol: str = "SPY") -> dict:
    """Compare a symbol's return + correlation vs a benchmark (default SPY).

    Args:
        symbol: Asset ticker.
        benchmark_symbol: Benchmark ticker (default SPY).

    Returns:
        Dict with symbol_return_pct, benchmark_return_pct, alpha,
        correlation_30d — or `{"error": ...}`.
    """
    try:
        asset_bars = _fetch_bars(symbol, _BENCHMARK_BARS)
        bench_bars = _fetch_bars(benchmark_symbol, _BENCHMARK_BARS)
        result = benchmark.compute_benchmark_comparison(asset_bars, bench_bars)
        return {"symbol": symbol, "benchmark": benchmark_symbol, **result}
    except Exception as e:
        log.warning(
            "compare_to_benchmark(%s, %s) failed: %s", symbol, benchmark_symbol, e
        )
        return {"error": str(e), "symbol": symbol, "benchmark": benchmark_symbol}
