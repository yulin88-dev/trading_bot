"""Lazy-initialized shared AlertStore for the tool layer.

Tools call get_alert_store(); tests inject a tmp_path-backed Store via
set_alert_store().
"""
from __future__ import annotations

from mcp_server.alerts.store import AlertStore

_store: AlertStore | None = None


def get_alert_store() -> AlertStore:
    global _store
    if _store is None:
        _store = AlertStore()
    return _store


def set_alert_store(store: AlertStore | None) -> None:
    global _store
    _store = store
