"""Unit tests for SMTP delivery — config, retry, dry-run, send_test, digest."""
from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest

from mcp_server.notifier import email as email_mod
from mcp_server.notifier import templates
from mcp_server.tools import notifier_tools


# --------------------------------------------------------------------- #
# Fixtures: env vars set + smtplib mocked                               #
# --------------------------------------------------------------------- #


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
    """Patch smtplib.SMTP so tests never hit the network."""
    smtp_instance = MagicMock()
    smtp_cm = MagicMock()
    smtp_cm.__enter__.return_value = smtp_instance
    smtp_cm.__exit__.return_value = False
    cls = mocker.patch.object(email_mod.smtplib, "SMTP", return_value=smtp_cm)
    return cls, smtp_instance


# --------------------------------------------------------------------- #
# Templates                                                             #
# --------------------------------------------------------------------- #


def _fire(symbol="TSLA", condition_type="price_below", params=None,
          observed=348.0, threshold=350.0,
          message="TSLA at $348", fired_at="2026-05-09T13:30:00Z"):
    return {
        "alert_id": "abc123",
        "symbol": symbol,
        "condition_type": condition_type,
        "params": params or {"target": threshold},
        "observed_value": observed,
        "threshold": threshold,
        "message": message,
        "fired_at": fired_at,
    }


class TestTemplates:
    def test_subject_includes_count_and_symbols(self):
        subj = templates.render_subject(
            [_fire(symbol="TSLA"), _fire(symbol="BTC")]
        )
        assert "[trading-bot]" in subj
        assert "2 alerts" in subj
        assert "BTC" in subj and "TSLA" in subj

    def test_subject_singular_form(self):
        assert "1 alert " in templates.render_subject([_fire()])

    def test_plaintext_includes_each_fire(self):
        text = templates.render_plaintext(
            [_fire(symbol="TSLA"), _fire(symbol="BTC")]
        )
        assert "TSLA" in text
        assert "BTC" in text
        assert "Fire #1" in text and "Fire #2" in text

    def test_html_escapes_payload(self):
        # symbol with HTML special chars should be escaped
        html = templates.render_html([_fire(symbol="<X>")])
        assert "<X>" not in html  # raw not present
        assert "&lt;X&gt;" in html

    def test_condition_label_combined(self):
        label = templates._condition_label(
            "combined_and",
            {
                "conditions": [
                    {"condition_type": "price_below", "params": {"target": 350}},
                    {"condition_type": "rsi_below", "params": {"threshold": 30}},
                ]
            },
        )
        assert "AND" in label
        assert "RSI" in label

    def test_build_digest_has_plain_and_html(self):
        msg = templates.build_digest([_fire()])
        assert msg["Subject"]
        # multipart with text/plain + text/html alternative
        parts = list(msg.iter_parts())
        types = {p.get_content_type() for p in parts}
        assert "text/plain" in types
        assert "text/html" in types


# --------------------------------------------------------------------- #
# Config                                                                #
# --------------------------------------------------------------------- #


class TestConfig:
    def test_get_config_ok(self, env):
        cfg = email_mod.get_config()
        assert cfg.host == "smtp.example.com"
        assert cfg.port == 587
        assert cfg.to_addrs == ["bob@example.com"]

    def test_to_list_split(self, env):
        env.setenv("ALERT_EMAIL_TO", "a@x.com, b@y.com ,c@z.com")
        assert email_mod.get_config().to_addrs == [
            "a@x.com", "b@y.com", "c@z.com"
        ]

    def test_missing_env_raises(self, env):
        env.delenv("SMTP_PASSWORD")
        with pytest.raises(RuntimeError) as exc:
            email_mod.get_config()
        assert "SMTP_PASSWORD" in str(exc.value)

    def test_is_configured(self, env):
        assert email_mod.is_configured() is True
        env.delenv("ALERT_EMAIL_TO")
        assert email_mod.is_configured() is False


# --------------------------------------------------------------------- #
# send_digest path                                                      #
# --------------------------------------------------------------------- #


class TestSendDigest:
    def test_dry_run_does_not_call_smtp(self, env, smtp_mock):
        cls, _ = smtp_mock
        result = email_mod.send_digest([_fire()], dry_run=True)
        assert result["sent"] is False
        assert result["dry_run"] is True
        assert "TSLA" in result["rendered"]
        cls.assert_not_called()

    def test_live_send_calls_smtp(self, env, smtp_mock):
        cls, smtp = smtp_mock
        result = email_mod.send_digest([_fire()])
        assert result["sent"] is True
        assert result["error"] is None
        cls.assert_called_once_with("smtp.example.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("alice@example.com", "supersecret")
        smtp.send_message.assert_called_once()
        # The sent message has From + To
        sent_msg = smtp.send_message.call_args.args[0]
        assert sent_msg["From"] == "alice@example.com"
        assert sent_msg["To"] == "bob@example.com"

    def test_rendered_contains_all_fires(self, env, smtp_mock):
        result = email_mod.send_digest(
            [_fire(symbol="TSLA"), _fire(symbol="BTC", threshold=80_000.0)]
        )
        assert "TSLA" in result["rendered"]
        assert "BTC" in result["rendered"]


# --------------------------------------------------------------------- #
# Retry                                                                 #
# --------------------------------------------------------------------- #


class TestRetry:
    def test_retries_once_on_transient(self, env, mocker):
        smtp_inst = MagicMock()
        smtp_cm_good = MagicMock()
        smtp_cm_good.__enter__.return_value = smtp_inst
        smtp_cm_good.__exit__.return_value = False

        # First call raises, second succeeds.
        cls = mocker.patch.object(email_mod.smtplib, "SMTP")
        cls.side_effect = [
            smtplib.SMTPServerDisconnected("transient"),
            smtp_cm_good,
        ]
        result = email_mod.send_digest([_fire()])
        assert result["sent"] is True
        assert cls.call_count == 2

    def test_no_retry_on_auth_failure(self, env, smtp_mock):
        cls, smtp = smtp_mock
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad auth")
        result = email_mod.send_digest([_fire()])
        assert result["sent"] is False
        assert "auth" in result["error"].lower() or "535" in result["error"]
        # Only one connect attempt — auth errors don't retry.
        assert cls.call_count == 1

    def test_gives_up_after_two_transient(self, env, mocker):
        cls = mocker.patch.object(email_mod.smtplib, "SMTP")
        cls.side_effect = [
            smtplib.SMTPServerDisconnected("first"),
            smtplib.SMTPServerDisconnected("second"),
        ]
        result = email_mod.send_digest([_fire()])
        assert result["sent"] is False
        assert "second" in result["error"]
        assert cls.call_count == 2


# --------------------------------------------------------------------- #
# send_test + send_test_email tool                                      #
# --------------------------------------------------------------------- #


class TestSendTest:
    def test_send_test_uses_default_to(self, env, smtp_mock):
        cls, smtp = smtp_mock
        result = email_mod.send_test()
        assert result["sent"] is True
        sent_msg = smtp.send_message.call_args.args[0]
        assert sent_msg["To"] == "bob@example.com"
        assert sent_msg["Subject"].startswith("[trading-bot]")

    def test_send_test_with_override(self, env, smtp_mock):
        _, smtp = smtp_mock
        result = email_mod.send_test(to="other@x.com", body="hi")
        sent_msg = smtp.send_message.call_args.args[0]
        assert sent_msg["To"] == "other@x.com"
        assert "hi" in sent_msg.as_string()
        assert result["sent"] is True

    def test_tool_wrapper_returns_error_on_missing_env(self, monkeypatch):
        # No env vars set.
        for k in email_mod.REQUIRED_ENV:
            monkeypatch.delenv(k, raising=False)
        result = notifier_tools.send_test_email()
        assert result["sent"] is False
        assert "missing env vars" in result["error"]

    def test_tool_wrapper_works_when_configured(self, env, smtp_mock):
        result = notifier_tools.send_test_email()
        assert result["sent"] is True


# --------------------------------------------------------------------- #
# Evaluator → email integration                                          #
# --------------------------------------------------------------------- #


class TestEvaluatorIntegration:
    def test_digest_sent_when_fires_and_configured(
        self, env, smtp_mock, tmp_path, mocker
    ):
        from mcp_server.alerts.evaluator import evaluate_alerts
        from mcp_server.alerts.store import AlertStore

        store = AlertStore(tmp_path / "alerts")
        store.add_alert("TSLA", "price_below", {"target": 350.0})

        # Mock data fetchers via a QuoteCache — re-use the FakeFetchers
        # idiom from test_evaluator.
        from mcp_server.alerts.evaluator import QuoteCache
        cache = QuoteCache(
            quote_fn=lambda sym: {"price": 348.0},
            history_fn=lambda sym, days: {"bars": []},
        )

        cls, smtp = smtp_mock
        result = evaluate_alerts(
            store=store, cache=cache,
            now=datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
        )
        assert result["fired"] == 1
        assert result["email"]["sent"] is True
        smtp.send_message.assert_called_once()

    def test_no_email_when_smtp_not_configured(self, monkeypatch, tmp_path, mocker):
        from mcp_server.alerts.evaluator import evaluate_alerts, QuoteCache
        from mcp_server.alerts.store import AlertStore

        for k in email_mod.REQUIRED_ENV:
            monkeypatch.delenv(k, raising=False)

        store = AlertStore(tmp_path / "alerts")
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        cache = QuoteCache(
            quote_fn=lambda sym: {"price": 348.0},
            history_fn=lambda sym, days: {"bars": []},
        )
        smtp_cls = mocker.patch.object(email_mod.smtplib, "SMTP")
        result = evaluate_alerts(store=store, cache=cache)
        assert result["fired"] == 1
        assert result["email"] is None
        smtp_cls.assert_not_called()

    def test_no_email_in_dry_run(self, env, tmp_path, mocker):
        from mcp_server.alerts.evaluator import evaluate_alerts, QuoteCache
        from mcp_server.alerts.store import AlertStore

        store = AlertStore(tmp_path / "alerts")
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        cache = QuoteCache(
            quote_fn=lambda sym: {"price": 348.0},
            history_fn=lambda sym, days: {"bars": []},
        )
        smtp_cls = mocker.patch.object(email_mod.smtplib, "SMTP")
        result = evaluate_alerts(store=store, cache=cache, dry_run=True)
        assert result["fired"] == 1
        assert result["email"] is None
        smtp_cls.assert_not_called()
