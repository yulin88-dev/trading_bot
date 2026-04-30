"""30-day annualized realized volatility + week-over-week delta."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _to_log_returns(bars: list[dict]) -> pd.Series:
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    closes = df["close"].astype(float)
    return np.log(closes / closes.shift(1)).dropna()


def compute_volatility(bars: list[dict], annualization: int = 252) -> dict:
    """Compute trailing-30 annualized vol vs prior-30 annualized vol.

    Args:
        bars: ascending-by-date list of OHLCV bars; needs >= 60 valid returns.
        annualization: 252 for trading-day series, 365 for calendar-day series.

    Returns:
        Dict with ann_vol_30d (%), ann_vol_prior_30d (%), vol_delta_pct (pp).
    """
    log_returns = _to_log_returns(bars)
    if len(log_returns) < 60:
        raise ValueError(
            f"Need at least 60 returns for 30+30 vol; got {len(log_returns)}"
        )

    last_30 = log_returns.iloc[-30:]
    prior_30 = log_returns.iloc[-60:-30]

    ann_vol_30d = float(last_30.std(ddof=1) * np.sqrt(annualization)) * 100.0
    ann_vol_prior_30d = float(prior_30.std(ddof=1) * np.sqrt(annualization)) * 100.0
    vol_delta_pct = ann_vol_30d - ann_vol_prior_30d

    return {
        "ann_vol_30d": ann_vol_30d,
        "ann_vol_prior_30d": ann_vol_prior_30d,
        "vol_delta_pct": vol_delta_pct,
    }
