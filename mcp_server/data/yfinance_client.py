"""yfinance fallback for stocks and BTC daily OHLCV."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import yfinance as yf


def get_bars(yf_symbol: str, days: int) -> list[dict]:
    """Daily OHLCV bars over `days` calendar days."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days * 2 + 5)

    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
    )
    if df.empty:
        return []

    df = df.tail(days)
    bars = []
    for idx, row in df.iterrows():
        bars.append(
            {
                "date": idx.date().isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
    return bars


def get_snapshot(yf_symbol: str) -> dict:
    """Latest snapshot — last price, 1-day change %, last volume.

    fast_info is unreliable for stocks (often returns 0 volume / no
    previous_close), so derive both from the last 2 daily bars.
    """
    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(period="5d", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance returned no history for {yf_symbol}")

    last = df.iloc[-1]
    price = float(last["Close"])
    volume = float(last["Volume"])
    as_of = last.name.to_pydatetime().astimezone(timezone.utc).isoformat()

    change_pct = None
    if len(df) >= 2:
        prev_close = float(df.iloc[-2]["Close"])
        if prev_close:
            change_pct = (price / prev_close - 1.0) * 100.0

    return {
        "price": price,
        "change_pct": change_pct,
        "volume": volume,
        "as_of": as_of,
    }
