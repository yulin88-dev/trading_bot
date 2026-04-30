"""CoinGecko client wrapper: BTC market chart and simple price.

Uses the free public API (no key required). The free `market_chart` endpoint
returns daily close + volume only, so OHLC is degraded — open=high=low=close
for each daily bar. For proper OHLC, the yfinance fallback should be used.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
TIMEOUT_SEC = 10


def _get(path: str, params: dict) -> dict:
    url = f"{COINGECKO_BASE}{path}"
    resp = requests.get(url, params=params, timeout=TIMEOUT_SEC)
    if resp.status_code == 429:
        raise RuntimeError("CoinGecko rate limit (429)")
    resp.raise_for_status()
    return resp.json()


def get_bars(coin_id: str, days: int) -> list[dict]:
    """Daily close-only bars (open=high=low=close) over `days` calendar days."""
    data = _get(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": days, "interval": "daily"},
    )
    prices = data.get("prices", [])
    volumes = {ts: v for ts, v in data.get("total_volumes", [])}

    # market_chart returns one point per day plus a partial "now" point at
    # the same date as today; dedupe by keeping the last value per date.
    by_date: dict[str, dict] = {}
    for ts_ms, close in prices:
        date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
        c = float(close)
        by_date[date] = {
            "date": date,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": float(volumes.get(ts_ms, 0.0)),
        }
    bars = sorted(by_date.values(), key=lambda b: b["date"])
    return bars[-days:]


def get_simple_price(coin_id: str) -> dict:
    """Latest price + 24h change + 24h volume."""
    data = _get(
        "/simple/price",
        {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_last_updated_at": "true",
        },
    )
    row = data.get(coin_id, {})
    if not row:
        raise RuntimeError(f"CoinGecko returned no data for {coin_id}")

    last_updated = row.get("last_updated_at")
    as_of = (
        datetime.fromtimestamp(last_updated, tz=timezone.utc).isoformat()
        if last_updated
        else datetime.now(timezone.utc).isoformat()
    )

    return {
        "price": float(row["usd"]),
        "change_pct": (
            float(row["usd_24h_change"]) if row.get("usd_24h_change") is not None else None
        ),
        "volume": (
            float(row["usd_24h_vol"]) if row.get("usd_24h_vol") is not None else None
        ),
        "as_of": as_of,
    }
