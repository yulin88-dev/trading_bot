"""MCP tool stubs for analysis. Real logic lands in Prompt 4."""
from __future__ import annotations


def compute_weekly_performance(symbol: str) -> dict:
    """Compute past-7d vs prior-7d performance.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with weekly_return_pct, week_high, week_low, avg_volume,
        prior_week_return_pct, delta_pp.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "weekly_return_pct": None,
        "week_high": None,
        "week_low": None,
        "avg_volume": None,
        "prior_week_return_pct": None,
        "delta_pp": None,
    }


def compute_technicals(symbol: str) -> dict:
    """Compute standard technical indicators (RSI, SMA, MACD).

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with rsi_14, sma_20, sma_50, macd_line, macd_signal, macd_hist,
        price_vs_sma20, price_vs_sma50, crossover_signal.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "rsi_14": None,
        "sma_20": None,
        "sma_50": None,
        "macd_line": None,
        "macd_signal": None,
        "macd_hist": None,
        "price_vs_sma20": None,
        "price_vs_sma50": None,
        "crossover_signal": None,
    }


def compute_volatility(symbol: str) -> dict:
    """Compute 30d annualized realized volatility and WoW delta.

    Args:
        symbol: Asset ticker.

    Returns:
        Dict with ann_vol_30d, ann_vol_prior_30d, vol_delta_pct.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "ann_vol_30d": None,
        "ann_vol_prior_30d": None,
        "vol_delta_pct": None,
    }


def compare_to_benchmark(symbol: str, benchmark: str = "SPY") -> dict:
    """Compare a symbol to a benchmark (default SPY).

    Args:
        symbol: Asset ticker.
        benchmark: Benchmark ticker (default SPY).

    Returns:
        Dict with symbol_return_pct, benchmark_return_pct, alpha, correlation_30d.
    """
    return {
        "_stub": True,
        "symbol": symbol,
        "benchmark": benchmark,
        "symbol_return_pct": None,
        "benchmark_return_pct": None,
        "alpha": None,
        "correlation_30d": None,
    }
