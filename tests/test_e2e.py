"""End-to-end smoke test for the v2 alert pipeline.

Seeds two alerts (one stock, one BTC), mocks the live data tools so one
fires and one doesn't, runs evaluate_alerts in dry-run + live modes,
asserts the rendered email body, and confirms cooldown logic suppresses
a repeat fire on the next evaluation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp_server.alerts.evaluator import QuoteCache, evaluate_alerts
from mcp_server.alerts.store import AlertStore
from mcp_server.notifier import email as email_mod


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "supersecret")
    monkeypatch.setenv("ALERT_EMAIL_FROM", "alice@example.com")
    monkeypatch.setenv("ALERT_EMAIL_TO", "bob@example.com")
    return monkeypatch


@pytest.fixture
def smtp_mock(mocker):
    smtp_instance = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = smtp_instance
    cm.__exit__.return_value = False
    cls = mocker.patch.object(email_mod.smtplib, "SMTP", return_value=cm)
    return cls, smtp_instance


def _bars(closes: list[float]) -> list[dict]:
    return [
        {"date": f"2026-04-{i+1:02d}", "open": c, "high": c, "low": c,
         "close": c, "volume": 1_000_000.0}
        for i, c in enumerate(closes)
    ]


def _seed_alerts(store: AlertStore) -> tuple[dict, dict]:
    """Two alerts: TSLA price_below 350 (will fire) + BTC price_above 90_000 (won't)."""
    tsla = store.add_alert(
        "TSLA", "price_below", {"target": 350.0}, cooldown_seconds=86400
    )
    btc = store.add_alert(
        "BTC", "price_above", {"target": 90_000.0}, cooldown_seconds=86400
    )
    return tsla, btc


def _cache_one_fires() -> QuoteCache:
    """TSLA below 350 (fires), BTC also at 75k so price_above 90k does not."""
    quotes = {"TSLA": {"price": 348.0}, "BTC": {"price": 75_000.0}}
    return QuoteCache(
        quote_fn=lambda sym: quotes.get(sym, {"error": f"no fake for {sym}"}),
        history_fn=lambda sym, days: {"bars": []},
    )


class TestEndToEndAlertPipeline:
    def test_dry_run_renders_email_without_persisting(
        self, env, smtp_mock, tmp_path
    ):
        store = AlertStore(tmp_path / "alerts")
        tsla, btc = _seed_alerts(store)
        cls, _ = smtp_mock

        result = evaluate_alerts(
            store=store, cache=_cache_one_fires(), dry_run=True
        )

        # Exactly one fire (TSLA), no SMTP call, no recorded fire.
        assert result["evaluated"] == 2
        assert result["fired"] == 1
        assert result["fires"][0]["symbol"] == "TSLA"
        assert result["dry_run"] is True
        assert result["email"] is None  # no email attempted in dry-run
        cls.assert_not_called()

        # Store unchanged: last_fired_at still None.
        assert store.get_alert(tsla["id"])["last_fired_at"] is None
        assert store.get_alert(btc["id"])["last_fired_at"] is None
        # fires.jsonl is empty
        assert store.fires_path.read_text() == ""

    def test_live_run_sends_digest_email_and_records(
        self, env, smtp_mock, tmp_path
    ):
        store = AlertStore(tmp_path / "alerts")
        tsla, btc = _seed_alerts(store)
        cls, smtp = smtp_mock

        result = evaluate_alerts(store=store, cache=_cache_one_fires())

        assert result["fired"] == 1
        assert result["email"]["sent"] is True

        # The rendered MIME contains both symbol + condition info.
        rendered = result["email"]["rendered"]
        assert "TSLA" in rendered
        assert "[trading-bot]" in rendered
        assert "price < $350" in rendered or "price &lt; $350" in rendered
        # "1 alert fired" appears in the subject and the body summary.
        assert "1 alert fired" in rendered

        # SMTP plumbing was exercised exactly once.
        cls.assert_called_once_with("smtp.example.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("alice@example.com", "supersecret")
        smtp.send_message.assert_called_once()

        # Persistence: alert.last_fired_at set; fires.jsonl has exactly one line.
        assert store.get_alert(tsla["id"])["last_fired_at"] is not None
        assert store.get_alert(btc["id"])["last_fired_at"] is None
        lines = store.fires_path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_cooldown_suppresses_repeat_fire(self, env, smtp_mock, tmp_path):
        store = AlertStore(tmp_path / "alerts")
        _seed_alerts(store)

        t0 = datetime(2026, 5, 8, 14, 30, tzinfo=timezone.utc)  # NYSE-open Friday

        # First pass at t0: fires + sends email + records.
        r1 = evaluate_alerts(store=store, cache=_cache_one_fires(), now=t0)
        assert r1["fired"] == 1

        # 30 min later, same conditions: cooldown is 24 h, so suppressed.
        r2 = evaluate_alerts(
            store=store,
            cache=_cache_one_fires(),
            now=t0 + timedelta(minutes=30),
        )
        assert r2["fired"] == 0
        assert r2["suppressed_by_cooldown"] == 1
        assert r2["email"] is None  # nothing to email

        # 25 hours later: cooldown elapsed → fires again.
        r3 = evaluate_alerts(
            store=store,
            cache=_cache_one_fires(),
            now=t0 + timedelta(hours=25),
        )
        assert r3["fired"] == 1
        assert r3["suppressed_by_cooldown"] == 0

        # Three SMTP send_message calls total: pass 1 (live), pass 3 (live).
        # (Pass 2 didn't send because nothing fired.)
        _, smtp = smtp_mock
        assert smtp.send_message.call_count == 2

        # fires.jsonl has two lines (one per real fire); pass 2 wrote nothing.
        lines = store.fires_path.read_text().strip().splitlines()
        assert len(lines) == 2
