"""Unit tests for analysis math.

Hand-calculated expected values where feasible; for indicators that need
recursive smoothing (RSI, MACD), tests use sequences with predictable
asymptotic behavior (monotonic up → RSI→100, flat → vol=0, etc.).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from mcp_server.analysis import benchmark, performance, technicals, volatility


def _bars(closes: list[float], start_date: str = "2026-01-01") -> list[dict]:
    """Build a minimal ascending-by-date OHLCV list from a close series."""
    dates = pd.date_range(start_date, periods=len(closes), freq="D")
    return [
        {
            "date": d.date().isoformat(),
            "open": float(c),
            "high": float(c),
            "low": float(c),
            "close": float(c),
            "volume": 1000.0,
        }
        for d, c in zip(dates, closes)
    ]


# ---------- performance ----------

class TestWeeklyPerformance:
    def test_simple_5pct_gain(self):
        # 8 closes — last 7 form "this week", no prior window
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 105.0]
        result = performance.compute_weekly_performance(_bars(closes), window=7)
        assert result["weekly_return_pct"] == pytest.approx(5.0)
        assert result["week_high"] == 105.0
        assert result["week_low"] == 100.0
        assert result["prior_week_return_pct"] is None

    def test_with_prior_week_comparison(self):
        # 14 closes — first 7 prior week (10% up), last 7 this week (5% down)
        prior = [100.0, 102.0, 104.0, 106.0, 108.0, 109.0, 110.0]
        this = [110.0, 108.0, 106.0, 105.0, 104.0, 105.0, 104.5]
        result = performance.compute_weekly_performance(_bars(prior + this), window=7)
        # this-week return = (104.5 / 110 - 1) * 100 = -5%
        assert result["weekly_return_pct"] == pytest.approx(-5.0, abs=0.01)
        # prior-week return = (110 / 100 - 1) * 100 = 10%
        assert result["prior_week_return_pct"] == pytest.approx(10.0)
        assert result["delta_pp"] == pytest.approx(-15.0, abs=0.01)

    def test_insufficient_data(self):
        with pytest.raises(ValueError):
            performance.compute_weekly_performance(_bars([100.0, 101.0]), window=7)


# ---------- technicals ----------

class TestSMA:
    def test_sma_5(self):
        closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        # SMA(3): NaN, NaN, 2.0, 3.0, 4.0, 5.0, 6.0
        result = technicals.sma(closes, 3).tolist()
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        assert result[2:] == [2.0, 3.0, 4.0, 5.0, 6.0]


class TestRSI:
    def test_monotonic_up_approaches_100(self):
        # 30 strictly increasing closes — RSI should be ~100 (no losses)
        closes = pd.Series([100.0 + i for i in range(30)])
        rsi_last = technicals.rsi(closes, 14).iloc[-1]
        assert rsi_last == pytest.approx(100.0, abs=0.001)

    def test_monotonic_down_approaches_0(self):
        closes = pd.Series([200.0 - i for i in range(30)])
        rsi_last = technicals.rsi(closes, 14).iloc[-1]
        assert rsi_last == pytest.approx(0.0, abs=0.001)


class TestMACD:
    def test_flat_series_yields_zero_macd(self):
        closes = pd.Series([100.0] * 50)
        m = technicals.macd(closes)
        assert m["macd"].iloc[-1] == pytest.approx(0.0)
        assert m["signal"].iloc[-1] == pytest.approx(0.0)
        assert m["histogram"].iloc[-1] == pytest.approx(0.0)

    def test_monotonic_up_positive_macd(self):
        closes = pd.Series([100.0 + i for i in range(60)])
        m = technicals.macd(closes)
        # In an uptrend, fast EMA > slow EMA, so MACD > 0
        assert m["macd"].iloc[-1] > 0


class TestComputeTechnicals:
    def test_returns_expected_shape(self):
        closes = [100.0 + 0.5 * i for i in range(60)]
        result = technicals.compute_technicals(_bars(closes))
        for key in (
            "rsi_14",
            "rsi_label",
            "sma_20",
            "sma_50",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "price_vs_sma20",
            "price_vs_sma50",
            "crossover_signal",
        ):
            assert key in result
        # Monotonic uptrend — last close above both SMAs, golden cross
        assert result["price_vs_sma20"] == "above"
        assert result["price_vs_sma50"] == "above"
        assert result["crossover_signal"].startswith("bullish")

    def test_insufficient_bars(self):
        with pytest.raises(ValueError):
            technicals.compute_technicals(_bars([100.0] * 49))


# ---------- volatility ----------

class TestVolatility:
    def test_flat_series_zero_vol(self):
        bars = _bars([100.0] * 70)
        result = volatility.compute_volatility(bars)
        assert result["ann_vol_30d"] == pytest.approx(0.0)
        assert result["ann_vol_prior_30d"] == pytest.approx(0.0)
        assert result["vol_delta_pct"] == pytest.approx(0.0)

    def test_known_std(self):
        # Build returns with hand-calculable variance.
        # Use 70 closes; the last 30 returns have a known std.
        # Daily log return alternating +0.01 and -0.01 → std ≈ 0.01
        # Annualized at 252: 0.01 * sqrt(252) ≈ 0.1587 → 15.87%
        closes = [100.0]
        for i in range(70):
            closes.append(closes[-1] * (math.exp(0.01) if i % 2 == 0 else math.exp(-0.01)))
        result = volatility.compute_volatility(_bars(closes), annualization=252)
        # Expected vol: std of [0.01, -0.01, 0.01, ...] (30 values) is sqrt(.0001) = 0.01
        # Sample std (ddof=1) on alternating ±0.01 → ~0.01017
        # * sqrt(252) ≈ 0.1614 → ~16.14%
        assert result["ann_vol_30d"] == pytest.approx(16.14, abs=0.5)

    def test_insufficient_bars(self):
        with pytest.raises(ValueError):
            volatility.compute_volatility(_bars([100.0] * 30))


# ---------- benchmark ----------

class TestBenchmarkComparison:
    def test_identical_series_correlation_one(self):
        closes = [100.0 + i * 0.3 for i in range(60)]
        bars = _bars(closes)
        result = benchmark.compute_benchmark_comparison(bars, bars)
        assert result["symbol_return_pct"] == pytest.approx(result["benchmark_return_pct"])
        assert result["alpha"] == pytest.approx(0.0)
        assert result["correlation_30d"] == pytest.approx(1.0, abs=1e-6)

    def test_inverse_returns_correlation_negative_one(self):
        # Correlation operates on pct-change, so build prices with returns that
        # are exact negations of each other.
        asset_returns = [0.01 if i % 2 == 0 else -0.01 for i in range(60)]
        bench_returns = [-r for r in asset_returns]
        asset_closes = [100.0]
        bench_closes = [100.0]
        for ar, br in zip(asset_returns, bench_returns):
            asset_closes.append(asset_closes[-1] * (1.0 + ar))
            bench_closes.append(bench_closes[-1] * (1.0 + br))
        result = benchmark.compute_benchmark_comparison(
            _bars(asset_closes), _bars(bench_closes)
        )
        assert result["correlation_30d"] == pytest.approx(-1.0, abs=1e-6)

    def test_alpha_calculation(self):
        # asset gains 20% over the window, bench gains 5% → alpha = 15pp
        asset_closes = list(np.linspace(100.0, 120.0, 35))
        bench_closes = list(np.linspace(100.0, 105.0, 35))
        result = benchmark.compute_benchmark_comparison(
            _bars(asset_closes), _bars(bench_closes)
        )
        assert result["symbol_return_pct"] == pytest.approx(20.0, abs=0.01)
        assert result["benchmark_return_pct"] == pytest.approx(5.0, abs=0.01)
        assert result["alpha"] == pytest.approx(15.0, abs=0.01)

    def test_inner_join_drops_unmatched_dates(self):
        asset = _bars([100.0 + i for i in range(40)], start_date="2026-01-01")
        # benchmark only covers half the dates
        bench = _bars([200.0 + i for i in range(20)], start_date="2026-01-15")
        result = benchmark.compute_benchmark_comparison(asset, bench)
        # alpha and correlation defined; just check no crash and shape
        assert "symbol_return_pct" in result
        assert "alpha" in result
