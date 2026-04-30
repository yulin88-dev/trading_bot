"""Benchmark comparison: relative return + 30-day correlation of daily returns."""
from __future__ import annotations

import pandas as pd


def _close_df(bars: list[dict], col: str) -> pd.DataFrame:
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "close"]].rename(columns={"close": col})


def compute_benchmark_comparison(
    asset_bars: list[dict],
    benchmark_bars: list[dict],
    correlation_window: int = 30,
) -> dict:
    """Compare an asset's return + correlation against a benchmark.

    Aligns the two series on dates with an inner merge (so weekend BTC bars
    are dropped when comparing to SPY).

    Args:
        asset_bars: ascending-by-date list of OHLCV bars for the asset.
        benchmark_bars: ascending-by-date list of OHLCV bars for the benchmark.
        correlation_window: number of overlapping bars used for correlation.

    Returns:
        Dict with symbol_return_pct, benchmark_return_pct, alpha,
        correlation_30d (None if insufficient overlap).
    """
    asset_df = _close_df(asset_bars, "close_asset")
    bench_df = _close_df(benchmark_bars, "close_bench")
    merged = asset_df.merge(bench_df, on="date", how="inner")

    if len(merged) < 2:
        raise ValueError("Insufficient overlapping bars for benchmark comparison")

    asset_return = (
        merged["close_asset"].iloc[-1] / merged["close_asset"].iloc[0] - 1.0
    ) * 100.0
    bench_return = (
        merged["close_bench"].iloc[-1] / merged["close_bench"].iloc[0] - 1.0
    ) * 100.0
    alpha = asset_return - bench_return

    correlation: float | None = None
    if len(merged) >= correlation_window + 1:
        recent = merged.tail(correlation_window + 1)
        a_ret = recent["close_asset"].pct_change().dropna()
        b_ret = recent["close_bench"].pct_change().dropna()
        correlation = float(a_ret.corr(b_ret))

    return {
        "symbol_return_pct": float(asset_return),
        "benchmark_return_pct": float(bench_return),
        "alpha": float(alpha),
        "correlation_30d": correlation,
    }
