"""Condition evaluators + evaluate_alerts orchestration.

Each evaluator returns a dict with:
- fired: bool
- observed_value: the live measurement (number, dict, or list for combined_*)
- threshold: the target (or None if not single-valued)
- message: human-readable summary
- error (optional): non-empty if data was missing or vendor failed

The orchestration:
- loads active alerts (filtered by symbol if given)
- shares a per-call QuoteCache so two alerts on the same symbol fetch
  data once
- for each fired alert: respects cooldown_seconds (gap from last_fired_at);
  records the fire (unless dry_run); leaves email-sending for Prompt 4
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from mcp_server.alerts.connection import get_alert_store
from mcp_server.alerts.store import AlertStore
from mcp_server.analysis.technicals import rsi, sma
from mcp_server.tools.data_tools import get_current_quote, get_price_history

log = logging.getLogger(__name__)


# --------------------------------------------------------------------- #
# Per-symbol quote cache                                                #
# --------------------------------------------------------------------- #


class QuoteCache:
    """Lazy per-symbol cache shared across one evaluation pass."""

    def __init__(
        self,
        quote_fn: Callable[[str], dict] | None = None,
        history_fn: Callable[[str, int], dict] | None = None,
    ) -> None:
        self._quote_fn = quote_fn or get_current_quote
        self._history_fn = history_fn or (lambda sym, days: get_price_history(sym, days=days))
        self._quotes: dict[str, dict] = {}
        self._history: dict[tuple[str, int], dict] = {}

    def quote(self, symbol: str) -> dict:
        if symbol not in self._quotes:
            self._quotes[symbol] = self._quote_fn(symbol)
        return self._quotes[symbol]

    def history(self, symbol: str, days: int) -> dict:
        # Re-use a wider cached window if available.
        for (sym, d), payload in self._history.items():
            if sym == symbol and d >= days and "error" not in payload:
                return payload
        key = (symbol, days)
        if key not in self._history:
            self._history[key] = self._history_fn(symbol, days)
        return self._history[key]


# --------------------------------------------------------------------- #
# Helpers                                                               #
# --------------------------------------------------------------------- #


def _missing_data(reason: str) -> dict:
    return {"fired": False, "observed_value": None, "threshold": None,
            "message": "", "error": reason}


def _closes_series(bars: list[dict]) -> pd.Series:
    return pd.Series([float(b["close"]) for b in bars])


def _bars_or_error(history: dict, min_len: int) -> tuple[list[dict] | None, str | None]:
    if "error" in history:
        return None, history["error"]
    bars = history.get("bars") or []
    if len(bars) < min_len:
        return None, f"insufficient history ({len(bars)} bars; need {min_len})"
    return bars, None


# --------------------------------------------------------------------- #
# Evaluators                                                            #
# --------------------------------------------------------------------- #


def eval_price_above(symbol: str, params: dict, cache: QuoteCache) -> dict:
    quote = cache.quote(symbol)
    if "error" in quote:
        return _missing_data(quote["error"])
    price = float(quote["price"])
    target = float(params["target"])
    fired = price > target
    return {
        "fired": fired,
        "observed_value": price,
        "threshold": target,
        "message": f"{symbol} at ${price:,.2f} {'above' if fired else 'at/below'} ${target:,.2f}",
    }


def eval_price_below(symbol: str, params: dict, cache: QuoteCache) -> dict:
    quote = cache.quote(symbol)
    if "error" in quote:
        return _missing_data(quote["error"])
    price = float(quote["price"])
    target = float(params["target"])
    fired = price < target
    return {
        "fired": fired,
        "observed_value": price,
        "threshold": target,
        "message": f"{symbol} at ${price:,.2f} {'below' if fired else 'at/above'} ${target:,.2f}",
    }


def eval_price_crosses_above(symbol: str, params: dict, cache: QuoteCache) -> dict:
    bars, err = _bars_or_error(cache.history(symbol, 5), min_len=2)
    if err:
        return _missing_data(err)
    today = float(bars[-1]["close"])
    prior = float(bars[-2]["close"])
    target = float(params["target"])
    fired = prior <= target < today
    return {
        "fired": fired,
        "observed_value": today,
        "threshold": target,
        "message": (
            f"{symbol} closed at ${today:,.2f}"
            + (f" (crossed above ${target:,.2f}; prior close ${prior:,.2f})" if fired
               else f"; prior close ${prior:,.2f} vs target ${target:,.2f}")
        ),
    }


def eval_price_crosses_below(symbol: str, params: dict, cache: QuoteCache) -> dict:
    bars, err = _bars_or_error(cache.history(symbol, 5), min_len=2)
    if err:
        return _missing_data(err)
    today = float(bars[-1]["close"])
    prior = float(bars[-2]["close"])
    target = float(params["target"])
    fired = prior >= target > today
    return {
        "fired": fired,
        "observed_value": today,
        "threshold": target,
        "message": (
            f"{symbol} closed at ${today:,.2f}"
            + (f" (crossed below ${target:,.2f}; prior close ${prior:,.2f})" if fired
               else f"; prior close ${prior:,.2f} vs target ${target:,.2f}")
        ),
    }


def eval_rsi_above(symbol: str, params: dict, cache: QuoteCache) -> dict:
    period = int(params.get("period", 14))
    threshold = float(params["threshold"])
    bars, err = _bars_or_error(cache.history(symbol, period * 3 + 5), min_len=period + 1)
    if err:
        return _missing_data(err)
    closes = _closes_series(bars)
    rsi_value = float(rsi(closes, period).iloc[-1])
    fired = rsi_value > threshold
    return {
        "fired": fired,
        "observed_value": rsi_value,
        "threshold": threshold,
        "message": f"{symbol} RSI({period}) at {rsi_value:.1f} {'above' if fired else 'at/below'} {threshold}",
    }


def eval_rsi_below(symbol: str, params: dict, cache: QuoteCache) -> dict:
    period = int(params.get("period", 14))
    threshold = float(params["threshold"])
    bars, err = _bars_or_error(cache.history(symbol, period * 3 + 5), min_len=period + 1)
    if err:
        return _missing_data(err)
    closes = _closes_series(bars)
    rsi_value = float(rsi(closes, period).iloc[-1])
    fired = rsi_value < threshold
    return {
        "fired": fired,
        "observed_value": rsi_value,
        "threshold": threshold,
        "message": f"{symbol} RSI({period}) at {rsi_value:.1f} {'below' if fired else 'at/above'} {threshold}",
    }


def _sma_cross(symbol: str, params: dict, cache: QuoteCache, direction: str) -> dict:
    fast = int(params["fast"])
    slow = int(params["slow"])
    if fast >= slow:
        return _missing_data(f"sma_cross requires fast<slow; got {fast},{slow}")
    needed = slow + 2
    bars, err = _bars_or_error(cache.history(symbol, needed + 5), min_len=needed)
    if err:
        return _missing_data(err)
    closes = _closes_series(bars)
    fast_series = sma(closes, fast)
    slow_series = sma(closes, slow)
    f_now, f_prev = float(fast_series.iloc[-1]), float(fast_series.iloc[-2])
    s_now, s_prev = float(slow_series.iloc[-1]), float(slow_series.iloc[-2])

    if direction == "above":
        fired = f_prev <= s_prev and f_now > s_now
        verb = "crossed above"
    else:  # "below"
        fired = f_prev >= s_prev and f_now < s_now
        verb = "crossed below"

    return {
        "fired": fired,
        "observed_value": {"fast_sma": f_now, "slow_sma": s_now},
        "threshold": {"fast_period": fast, "slow_period": slow},
        "message": (
            f"{symbol} SMA({fast})={f_now:,.2f} {verb if fired else 'currently'} "
            f"SMA({slow})={s_now:,.2f}"
        ),
    }


def eval_sma_cross_above(symbol: str, params: dict, cache: QuoteCache) -> dict:
    return _sma_cross(symbol, params, cache, "above")


def eval_sma_cross_below(symbol: str, params: dict, cache: QuoteCache) -> dict:
    return _sma_cross(symbol, params, cache, "below")


def eval_daily_change_pct_above(symbol: str, params: dict, cache: QuoteCache) -> dict:
    quote = cache.quote(symbol)
    if "error" in quote:
        return _missing_data(quote["error"])
    change_pct = quote.get("change_pct")
    if change_pct is None:
        return _missing_data("daily change unavailable from quote")
    pct = float(params["pct"])
    fired = float(change_pct) > pct
    return {
        "fired": fired,
        "observed_value": float(change_pct),
        "threshold": pct,
        "message": f"{symbol} daily change {change_pct:+.2f}% {'above' if fired else 'at/below'} {pct:+.2f}%",
    }


def eval_daily_change_pct_below(symbol: str, params: dict, cache: QuoteCache) -> dict:
    quote = cache.quote(symbol)
    if "error" in quote:
        return _missing_data(quote["error"])
    change_pct = quote.get("change_pct")
    if change_pct is None:
        return _missing_data("daily change unavailable from quote")
    pct = float(params["pct"])
    fired = float(change_pct) < pct
    return {
        "fired": fired,
        "observed_value": float(change_pct),
        "threshold": pct,
        "message": f"{symbol} daily change {change_pct:+.2f}% {'below' if fired else 'at/above'} {pct:+.2f}%",
    }


def eval_volume_above_avg(symbol: str, params: dict, cache: QuoteCache) -> dict:
    multiplier = float(params["multiplier"])
    lookback = int(params.get("lookback_days", 20))
    bars, err = _bars_or_error(cache.history(symbol, lookback + 5), min_len=lookback + 1)
    if err:
        return _missing_data(err)
    today_vol = float(bars[-1]["volume"])
    prior_vols = [float(b["volume"]) for b in bars[-(lookback + 1):-1]]
    avg_vol = sum(prior_vols) / lookback
    threshold = avg_vol * multiplier
    fired = today_vol > threshold
    return {
        "fired": fired,
        "observed_value": today_vol,
        "threshold": threshold,
        "message": (
            f"{symbol} volume {today_vol:,.0f} "
            f"{'above' if fired else 'at/below'} {multiplier}× {lookback}-day avg "
            f"({avg_vol:,.0f})"
        ),
    }


def eval_combined_and(symbol: str, params: dict, cache: QuoteCache) -> dict:
    nested_results = []
    for cond in params["conditions"]:
        nested_results.append(_eval(cond["condition_type"], symbol, cond.get("params") or {}, cache))
    if any("error" in r for r in nested_results):
        first_err = next(r["error"] for r in nested_results if r.get("error"))
        return {**_missing_data(first_err), "nested": nested_results}
    fired = all(r["fired"] for r in nested_results)
    return {
        "fired": fired,
        "observed_value": [r["observed_value"] for r in nested_results],
        "threshold": [r["threshold"] for r in nested_results],
        "message": " AND ".join(r["message"] for r in nested_results),
        "nested": nested_results,
    }


def eval_combined_or(symbol: str, params: dict, cache: QuoteCache) -> dict:
    nested_results = []
    for cond in params["conditions"]:
        nested_results.append(_eval(cond["condition_type"], symbol, cond.get("params") or {}, cache))
    # OR fires if any nested fired, even if some others errored.
    fired = any(r["fired"] for r in nested_results)
    if not fired and all("error" in r for r in nested_results):
        return {**_missing_data(nested_results[0]["error"]), "nested": nested_results}
    return {
        "fired": fired,
        "observed_value": [r["observed_value"] for r in nested_results],
        "threshold": [r["threshold"] for r in nested_results],
        "message": " OR ".join(r["message"] for r in nested_results if not r.get("error")),
        "nested": nested_results,
    }


EVALUATORS: dict[str, Callable[[str, dict, QuoteCache], dict]] = {
    "price_above": eval_price_above,
    "price_below": eval_price_below,
    "price_crosses_above": eval_price_crosses_above,
    "price_crosses_below": eval_price_crosses_below,
    "rsi_above": eval_rsi_above,
    "rsi_below": eval_rsi_below,
    "sma_cross_above": eval_sma_cross_above,
    "sma_cross_below": eval_sma_cross_below,
    "daily_change_pct_above": eval_daily_change_pct_above,
    "daily_change_pct_below": eval_daily_change_pct_below,
    "volume_above_avg": eval_volume_above_avg,
    "combined_and": eval_combined_and,
    "combined_or": eval_combined_or,
}


def _eval(condition_type: str, symbol: str, params: dict, cache: QuoteCache) -> dict:
    fn = EVALUATORS.get(condition_type)
    if fn is None:
        return _missing_data(f"unknown condition_type: {condition_type}")
    return fn(symbol, params, cache)


# --------------------------------------------------------------------- #
# Orchestration                                                         #
# --------------------------------------------------------------------- #


def _parse_iso(ts: str) -> datetime:
    # Accept the trailing-Z form we write in the store.
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def evaluate_alerts(
    symbol: str | None = None,
    dry_run: bool = False,
    *,
    now: datetime | None = None,
    store: AlertStore | None = None,
    cache: QuoteCache | None = None,
) -> dict:
    """One evaluation pass across all active alerts.

    Args:
        symbol: optional filter — only evaluate alerts on this symbol.
        dry_run: if True, do not persist fires (or — once Prompt 4 lands —
            send emails). The returned `fires` list still describes what
            would have happened.
        now: optional clock override (used for cooldown math; useful in tests).
        store: optional AlertStore override (tests inject a tmp_path store).
        cache: optional QuoteCache override (tests inject mock fetchers).

    Returns:
        Dict with evaluated, fired, suppressed_by_cooldown, errors, fires.
    """
    now = now or datetime.now(timezone.utc)
    store = store or get_alert_store()
    cache = cache or QuoteCache()

    alerts = store.list_alerts(status="active")
    if symbol:
        alerts = [a for a in alerts if a["symbol"] == symbol]

    fires: list[dict] = []
    errors: list[str] = []
    suppressed = 0

    for alert in alerts:
        try:
            result = _eval(alert["condition_type"], alert["symbol"], alert["params"], cache)
        except Exception as e:
            log.exception("evaluator crashed")
            errors.append(f"{alert['id']} ({alert['symbol']} {alert['condition_type']}): {e}")
            continue

        if result.get("error"):
            errors.append(
                f"{alert['id']} ({alert['symbol']} {alert['condition_type']}): {result['error']}"
            )
            continue
        if not result["fired"]:
            continue

        # Cooldown
        last_fired = alert.get("last_fired_at")
        if last_fired:
            elapsed = (now - _parse_iso(last_fired)).total_seconds()
            if elapsed < alert["cooldown_seconds"]:
                suppressed += 1
                continue

        fire = {
            "alert_id": alert["id"],
            "symbol": alert["symbol"],
            "condition_type": alert["condition_type"],
            "params": alert["params"],
            "observed_value": result["observed_value"],
            "threshold": result["threshold"],
            "message": result["message"],
            "fired_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if not dry_run:
            store.record_fire(
                alert["id"],
                {
                    "observed_value": result["observed_value"],
                    "threshold": result["threshold"],
                },
                result["message"],
                now=now,
            )
        fires.append(fire)

    return {
        "evaluated": len(alerts),
        "fired": len(fires),
        "suppressed_by_cooldown": suppressed,
        "errors": errors,
        "fires": fires,
        "dry_run": dry_run,
    }
