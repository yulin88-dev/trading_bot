"""Unit tests for v2 alert condition evaluators + evaluate_alerts orchestration.

Tests use mocked data tools (no network) and an explicit `now` clock so
cooldown logic is deterministic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from mcp_server.alerts.evaluator import (
    EVALUATORS,
    QuoteCache,
    evaluate_alerts,
)
from mcp_server.alerts.store import AlertStore


# --------------------------------------------------------------------- #
# Fixtures: a fake QuoteCache that returns canned data per symbol       #
# --------------------------------------------------------------------- #


class FakeFetchers:
    """Helper that builds quote_fn / history_fn for a QuoteCache."""

    def __init__(
        self,
        quotes: dict[str, dict] | None = None,
        histories: dict[str, list[dict]] | None = None,
    ) -> None:
        self.quotes = quotes or {}
        self.histories = histories or {}
        self.quote_calls: list[str] = []
        self.history_calls: list[tuple[str, int]] = []

    def quote_fn(self, symbol: str) -> dict:
        self.quote_calls.append(symbol)
        return self.quotes.get(symbol, {"error": f"no fake quote for {symbol}"})

    def history_fn(self, symbol: str, days: int) -> dict:
        self.history_calls.append((symbol, days))
        bars = self.histories.get(symbol)
        if bars is None:
            return {"error": f"no fake history for {symbol}"}
        return {"symbol": symbol, "source": "fake", "bars": bars[-days:]}

    def cache(self) -> QuoteCache:
        return QuoteCache(self.quote_fn, self.history_fn)


def _bars(closes: list[float], volumes: list[float] | None = None) -> list[dict]:
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    return [
        {
            "date": f"2026-01-{i + 1:02d}",
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": v,
        }
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


# --------------------------------------------------------------------- #
# Per-condition evaluators                                              #
# --------------------------------------------------------------------- #


class TestPriceCompare:
    def test_price_below_fires(self):
        cache = FakeFetchers(quotes={"TSLA": {"price": 348.0}}).cache()
        r = EVALUATORS["price_below"]("TSLA", {"target": 350.0}, cache)
        assert r["fired"] is True
        assert r["observed_value"] == 348.0
        assert r["threshold"] == 350.0

    def test_price_below_no_fire_at_target(self):
        cache = FakeFetchers(quotes={"TSLA": {"price": 350.0}}).cache()
        r = EVALUATORS["price_below"]("TSLA", {"target": 350.0}, cache)
        assert r["fired"] is False

    def test_price_above_fires(self):
        cache = FakeFetchers(quotes={"BTC": {"price": 81_000.0}}).cache()
        r = EVALUATORS["price_above"]("BTC", {"target": 80_000.0}, cache)
        assert r["fired"] is True

    def test_quote_error_propagates(self):
        cache = FakeFetchers(quotes={"X": {"error": "vendor down"}}).cache()
        r = EVALUATORS["price_below"]("X", {"target": 1.0}, cache)
        assert r["fired"] is False
        assert r["error"] == "vendor down"


class TestPriceCrosses:
    def test_crosses_above_fires(self):
        cache = FakeFetchers(histories={"TSLA": _bars([348.0, 352.0])}).cache()
        r = EVALUATORS["price_crosses_above"]("TSLA", {"target": 350.0}, cache)
        assert r["fired"] is True
        assert r["observed_value"] == 352.0

    def test_crosses_above_no_fire_when_already_above(self):
        cache = FakeFetchers(histories={"TSLA": _bars([351.0, 352.0])}).cache()
        r = EVALUATORS["price_crosses_above"]("TSLA", {"target": 350.0}, cache)
        assert r["fired"] is False

    def test_crosses_below_fires(self):
        cache = FakeFetchers(histories={"TSLA": _bars([352.0, 348.0])}).cache()
        r = EVALUATORS["price_crosses_below"]("TSLA", {"target": 350.0}, cache)
        assert r["fired"] is True

    def test_insufficient_history_returns_error(self):
        cache = FakeFetchers(histories={"TSLA": _bars([350.0])}).cache()
        r = EVALUATORS["price_crosses_above"]("TSLA", {"target": 349.0}, cache)
        assert "error" in r and r["fired"] is False


class TestRSI:
    def test_rsi_below_fires_on_strong_downtrend(self):
        # Strictly decreasing → RSI → 0 (well under any sane threshold).
        bars = _bars([200.0 - i for i in range(40)])
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["rsi_below"]("X", {"threshold": 30}, cache)
        assert r["fired"] is True
        assert r["observed_value"] < 5  # essentially zero

    def test_rsi_above_fires_on_strong_uptrend(self):
        bars = _bars([100.0 + i for i in range(40)])
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["rsi_above"]("X", {"threshold": 70}, cache)
        assert r["fired"] is True
        assert r["observed_value"] > 95

    def test_custom_period_accepted(self):
        bars = _bars([100.0 + i for i in range(40)])
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["rsi_above"]("X", {"threshold": 70, "period": 7}, cache)
        assert r["fired"] is True


class TestSMACross:
    def test_cross_above_fires(self):
        # 30 flat bars (fast SMA == slow SMA at penultimate) then a single
        # sharp up bar that pulls fast above slow. Cross above fires.
        closes = [100.0] * 30 + [200.0]
        bars = _bars(closes)
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["sma_cross_above"]("X", {"fast": 5, "slow": 20}, cache)
        assert r["fired"] is True
        assert "fast_sma" in r["observed_value"]

    def test_cross_below_fires(self):
        # 30 flat bars then a single sharp down bar.
        closes = [100.0] * 30 + [50.0]
        bars = _bars(closes)
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["sma_cross_below"]("X", {"fast": 5, "slow": 20}, cache)
        assert r["fired"] is True

    def test_no_fire_when_no_cross(self):
        closes = [100.0 + i for i in range(40)]  # steady uptrend, fast already above slow
        bars = _bars(closes)
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["sma_cross_above"]("X", {"fast": 5, "slow": 20}, cache)
        assert r["fired"] is False

    def test_fast_must_be_less_than_slow(self):
        bars = _bars([100.0] * 40)
        cache = FakeFetchers(histories={"X": bars}).cache()
        r = EVALUATORS["sma_cross_above"]("X", {"fast": 20, "slow": 5}, cache)
        assert "error" in r


class TestDailyChangePct:
    def test_above_fires(self):
        cache = FakeFetchers(quotes={"X": {"price": 100, "change_pct": 3.5}}).cache()
        r = EVALUATORS["daily_change_pct_above"]("X", {"pct": 2.0}, cache)
        assert r["fired"] is True
        assert r["observed_value"] == 3.5

    def test_below_fires_on_negative(self):
        cache = FakeFetchers(quotes={"X": {"price": 100, "change_pct": -4.0}}).cache()
        r = EVALUATORS["daily_change_pct_below"]("X", {"pct": -3.0}, cache)
        assert r["fired"] is True

    def test_missing_change_pct_returns_error(self):
        cache = FakeFetchers(quotes={"X": {"price": 100, "change_pct": None}}).cache()
        r = EVALUATORS["daily_change_pct_above"]("X", {"pct": 1}, cache)
        assert "error" in r


class TestVolumeAboveAvg:
    def test_fires_when_volume_spikes(self):
        # 21 bars: 20 baseline @ 1M, last @ 5M (5× avg)
        closes = [100.0] * 21
        volumes = [1_000_000.0] * 20 + [5_000_000.0]
        cache = FakeFetchers(histories={"X": _bars(closes, volumes)}).cache()
        r = EVALUATORS["volume_above_avg"]("X", {"multiplier": 2.0}, cache)
        assert r["fired"] is True
        assert r["observed_value"] == 5_000_000.0
        # threshold = avg * multiplier = 1M * 2 = 2M
        assert r["threshold"] == 2_000_000.0

    def test_no_fire_when_volume_normal(self):
        closes = [100.0] * 21
        volumes = [1_000_000.0] * 20 + [1_500_000.0]
        cache = FakeFetchers(histories={"X": _bars(closes, volumes)}).cache()
        r = EVALUATORS["volume_above_avg"]("X", {"multiplier": 2.0}, cache)
        assert r["fired"] is False


class TestCombined:
    def test_and_all_fire(self):
        cache = FakeFetchers(
            quotes={"TSLA": {"price": 348.0}},
            histories={"TSLA": _bars([200.0 - i for i in range(40)])},
        ).cache()
        r = EVALUATORS["combined_and"](
            "TSLA",
            {
                "conditions": [
                    {"condition_type": "price_below", "params": {"target": 350.0}},
                    {"condition_type": "rsi_below", "params": {"threshold": 30}},
                ]
            },
            cache,
        )
        assert r["fired"] is True

    def test_and_one_misses(self):
        cache = FakeFetchers(
            quotes={"TSLA": {"price": 348.0}},
            histories={"TSLA": _bars([100.0 + i for i in range(40)])},
        ).cache()
        r = EVALUATORS["combined_and"](
            "TSLA",
            {
                "conditions": [
                    {"condition_type": "price_below", "params": {"target": 350.0}},
                    # RSI at ~100 won't be below 30
                    {"condition_type": "rsi_below", "params": {"threshold": 30}},
                ]
            },
            cache,
        )
        assert r["fired"] is False

    def test_or_one_fires(self):
        cache = FakeFetchers(
            quotes={"TSLA": {"price": 360.0}},  # not below 350
            histories={"TSLA": _bars([200.0 - i for i in range(40)])},  # but RSI is low
        ).cache()
        r = EVALUATORS["combined_or"](
            "TSLA",
            {
                "conditions": [
                    {"condition_type": "price_below", "params": {"target": 350.0}},
                    {"condition_type": "rsi_below", "params": {"threshold": 30}},
                ]
            },
            cache,
        )
        assert r["fired"] is True


# --------------------------------------------------------------------- #
# QuoteCache deduplication                                              #
# --------------------------------------------------------------------- #


class TestQuoteCache:
    def test_quote_fetched_once_per_symbol(self):
        f = FakeFetchers(quotes={"TSLA": {"price": 350}})
        cache = f.cache()
        cache.quote("TSLA")
        cache.quote("TSLA")
        cache.quote("TSLA")
        assert f.quote_calls == ["TSLA"]

    def test_history_reused_when_wider_window_cached(self):
        f = FakeFetchers(histories={"X": _bars([1.0] * 50)})
        cache = f.cache()
        cache.history("X", 50)
        cache.history("X", 20)  # subset, should reuse
        # only one history fetch
        assert len(f.history_calls) == 1


# --------------------------------------------------------------------- #
# evaluate_alerts orchestration                                         #
# --------------------------------------------------------------------- #


@pytest.fixture
def store(tmp_path: Path) -> AlertStore:
    return AlertStore(tmp_path / "alerts")


class TestEvaluateAlerts:
    def test_runs_active_alerts_and_records_fires(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        result = evaluate_alerts(store=store, cache=f.cache())
        assert result["evaluated"] == 1
        assert result["fired"] == 1
        # last_fired_at on the alert should now be set
        assert store.get_alert(a["id"])["last_fired_at"] is not None

    def test_dry_run_does_not_record(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        result = evaluate_alerts(store=store, cache=f.cache(), dry_run=True)
        assert result["fired"] == 1
        assert result["dry_run"] is True
        assert store.get_alert(a["id"])["last_fired_at"] is None

    def test_skips_paused_alerts(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        store.pause_alert(a["id"])
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        result = evaluate_alerts(store=store, cache=f.cache())
        assert result["evaluated"] == 0
        assert result["fired"] == 0

    def test_filter_by_symbol(self, store):
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        store.add_alert("BTC", "price_above", {"target": 80_000.0})
        f = FakeFetchers(
            quotes={"TSLA": {"price": 348.0}, "BTC": {"price": 81_000.0}}
        )
        # Only TSLA evaluated.
        result = evaluate_alerts(store=store, cache=f.cache(), symbol="TSLA")
        assert result["evaluated"] == 1
        assert result["fires"][0]["symbol"] == "TSLA"

    def test_cooldown_suppresses_repeat_fire(self, store):
        a = store.add_alert(
            "TSLA", "price_below", {"target": 350.0}, cooldown_seconds=3600
        )
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        t0 = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
        # First pass: fires.
        r1 = evaluate_alerts(store=store, cache=f.cache(), now=t0)
        assert r1["fired"] == 1
        # 30 min later: cooldown still active.
        r2 = evaluate_alerts(
            store=store, cache=f.cache(), now=t0 + timedelta(minutes=30)
        )
        assert r2["fired"] == 0
        assert r2["suppressed_by_cooldown"] == 1
        # 2 hours later: cooldown elapsed, fires again.
        r3 = evaluate_alerts(
            store=store, cache=f.cache(), now=t0 + timedelta(hours=2)
        )
        assert r3["fired"] == 1

    def test_quote_cache_dedups_across_alerts(self, store):
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        store.add_alert("TSLA", "price_above", {"target": 100.0})
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        cache = f.cache()
        evaluate_alerts(store=store, cache=cache)
        # Two alerts, same symbol → quote fetched once.
        assert f.quote_calls == ["TSLA"]

    def test_collects_errors_without_aborting(self, store):
        store.add_alert("X", "price_below", {"target": 1.0})  # no fake quote → error
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        result = evaluate_alerts(store=store, cache=f.cache())
        assert result["fired"] == 1
        assert any("X" in e for e in result["errors"])

    def test_evaluator_crash_is_caught(self, store, monkeypatch):
        store.add_alert("TSLA", "price_below", {"target": 350.0})

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setitem(EVALUATORS, "price_below", boom)
        f = FakeFetchers(quotes={"TSLA": {"price": 348.0}})
        result = evaluate_alerts(store=store, cache=f.cache())
        assert result["fired"] == 0
        assert any("boom" in e for e in result["errors"])
