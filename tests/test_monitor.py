"""Unit tests for the launchd monitor entry point."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mcp_server import monitor


@pytest.fixture
def isolated_alerts(tmp_path, monkeypatch):
    """Point the alerts store at a tmp_path so monitor.main doesn't touch reports/."""
    monkeypatch.setattr(
        "mcp_server.alerts.store.ALERTS_DIR", tmp_path / "alerts"
    )
    monkeypatch.setattr(
        "mcp_server.alerts.store.ALERTS_FILE", tmp_path / "alerts" / "alerts.json"
    )
    monkeypatch.setattr(
        "mcp_server.alerts.store.FIRES_FILE", tmp_path / "alerts" / "fires.jsonl"
    )
    return tmp_path


class TestMonitorMain:
    def test_skips_when_market_closed(self, isolated_alerts, mocker):
        mocker.patch.object(monitor, "is_market_open", return_value=False)
        eval_mock = mocker.patch.object(monitor, "evaluate_alerts")
        rc = monitor.main()
        assert rc == 0
        eval_mock.assert_not_called()

    def test_calls_evaluate_when_market_open(self, isolated_alerts, mocker):
        mocker.patch.object(monitor, "is_market_open", return_value=True)
        eval_mock = mocker.patch.object(
            monitor,
            "evaluate_alerts",
            return_value={
                "evaluated": 2, "fired": 1, "suppressed_by_cooldown": 0,
                "errors": [], "fires": [], "email": None,
            },
        )
        now = datetime(2026, 5, 8, 14, 30, tzinfo=timezone.utc)
        rc = monitor.main(now=now)
        assert rc == 0
        eval_mock.assert_called_once()
        # dry_run defaulted to False
        assert eval_mock.call_args.kwargs["dry_run"] is False
        assert eval_mock.call_args.kwargs["now"] == now

    def test_dry_run_propagates(self, isolated_alerts, mocker):
        mocker.patch.object(monitor, "is_market_open", return_value=True)
        eval_mock = mocker.patch.object(
            monitor,
            "evaluate_alerts",
            return_value={
                "evaluated": 0, "fired": 0, "suppressed_by_cooldown": 0,
                "errors": [], "fires": [], "email": None,
            },
        )
        monitor.main(dry_run=True)
        assert eval_mock.call_args.kwargs["dry_run"] is True

    def test_logs_email_failure(self, isolated_alerts, mocker, caplog):
        import logging

        # setup_logging() wipes root handlers (incl. caplog's); patch to no-op.
        mocker.patch.object(monitor, "setup_logging")
        mocker.patch.object(monitor, "is_market_open", return_value=True)
        mocker.patch.object(
            monitor,
            "evaluate_alerts",
            return_value={
                "evaluated": 1, "fired": 1, "suppressed_by_cooldown": 0,
                "errors": [], "fires": [],
                "email": {"sent": False, "error": "auth failed"},
            },
        )
        with caplog.at_level(logging.WARNING, logger="mcp_server.monitor"):
            monitor.main()
        assert any("auth failed" in r.message for r in caplog.records)

    def test_logs_eval_errors(self, isolated_alerts, mocker, caplog):
        import logging

        mocker.patch.object(monitor, "setup_logging")
        mocker.patch.object(monitor, "is_market_open", return_value=True)
        mocker.patch.object(
            monitor,
            "evaluate_alerts",
            return_value={
                "evaluated": 1, "fired": 0, "suppressed_by_cooldown": 0,
                "errors": ["foo: vendor down"], "fires": [], "email": None,
            },
        )
        with caplog.at_level(logging.WARNING, logger="mcp_server.monitor"):
            monitor.main()
        assert any("vendor down" in r.message for r in caplog.records)
