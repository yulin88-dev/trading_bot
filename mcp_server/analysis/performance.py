"""Weekly performance: past-N vs prior-N return, high, low, average volume."""
from __future__ import annotations

import pandas as pd


def _to_df(bars: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def compute_weekly_performance(bars: list[dict], window: int = 7) -> dict:
    """Return weekly performance metrics.

    "Weekly" here means a window of `window` bars (default 7). For stock
    symbols where bars are trading days, callers may want to pass window=5.

    Args:
        bars: ascending-by-date list of OHLCV bars.
        window: number of bars per week.

    Returns:
        Dict with weekly_return_pct, week_high, week_low, avg_volume,
        prior_week_return_pct, delta_pp.

    Raises:
        ValueError: fewer than `window + 1` bars supplied.
    """
    if len(bars) < window + 1:
        raise ValueError(
            f"Need at least {window + 1} bars to compute weekly return; got {len(bars)}"
        )
    df = _to_df(bars)

    this_week = df.tail(window)
    weekly_return_pct = (this_week["close"].iloc[-1] / this_week["close"].iloc[0] - 1.0) * 100.0
    week_high = float(this_week["high"].max())
    week_low = float(this_week["low"].min())
    avg_volume = float(this_week["volume"].mean())

    prior_week_return_pct: float | None = None
    delta_pp: float | None = None
    if len(df) >= 2 * window:
        prior = df.iloc[-2 * window : -window]
        prior_week_return_pct = (
            prior["close"].iloc[-1] / prior["close"].iloc[0] - 1.0
        ) * 100.0
        delta_pp = weekly_return_pct - prior_week_return_pct

    return {
        "weekly_return_pct": float(weekly_return_pct),
        "week_high": week_high,
        "week_low": week_low,
        "avg_volume": avg_volume,
        "prior_week_return_pct": (
            float(prior_week_return_pct) if prior_week_return_pct is not None else None
        ),
        "delta_pp": float(delta_pp) if delta_pp is not None else None,
    }
