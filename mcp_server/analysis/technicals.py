"""Technical indicators: RSI(14), SMA(20/50), MACD(12,26,9)."""
from __future__ import annotations

import pandas as pd


def _to_close_series(bars: list[dict]) -> pd.Series:
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df["close"].astype(float)


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI.

    Uses an EMA with alpha = 1/period, equivalent to Wilder's smoothing.
    """
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def sma(closes: pd.Series, period: int) -> pd.Series:
    return closes.rolling(window=period).mean()


def macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """Standard MACD: 12/26 EMA difference, 9-period signal EMA."""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def _rsi_label(value: float) -> str:
    if value >= 70.0:
        return "overbought"
    if value <= 30.0:
        return "oversold"
    return "neutral"


def _crossover_signal(sma_20_last: float, sma_50_last: float) -> str:
    if sma_20_last > sma_50_last:
        return "bullish (SMA20 > SMA50)"
    if sma_20_last < sma_50_last:
        return "bearish (SMA20 < SMA50)"
    return "neutral (SMA20 == SMA50)"


def compute_technicals(bars: list[dict]) -> dict:
    """Compute RSI(14), SMA(20), SMA(50), and MACD(12,26,9) at the latest bar.

    Args:
        bars: ascending-by-date list of OHLCV bars; needs >= 50 bars.

    Returns:
        Dict with rsi_14, rsi_label, sma_20, sma_50, macd_line, macd_signal,
        macd_hist, price_vs_sma20, price_vs_sma50, crossover_signal.
    """
    if len(bars) < 50:
        raise ValueError(f"Need at least 50 bars for SMA(50); got {len(bars)}")

    closes = _to_close_series(bars)
    last_close = float(closes.iloc[-1])

    rsi_14 = float(rsi(closes, 14).iloc[-1])
    sma_20 = float(sma(closes, 20).iloc[-1])
    sma_50 = float(sma(closes, 50).iloc[-1])

    m = macd(closes)
    macd_line = float(m["macd"].iloc[-1])
    macd_signal = float(m["signal"].iloc[-1])
    macd_hist = float(m["histogram"].iloc[-1])

    return {
        "rsi_14": rsi_14,
        "rsi_label": _rsi_label(rsi_14),
        "sma_20": sma_20,
        "sma_50": sma_50,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "price_vs_sma20": "above" if last_close > sma_20 else "below",
        "price_vs_sma50": "above" if last_close > sma_50 else "below",
        "crossover_signal": _crossover_signal(sma_20, sma_50),
    }
