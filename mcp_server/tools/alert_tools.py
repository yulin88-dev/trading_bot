"""MCP tools for v2 alert CRUD + (Prompt 4 stub) evaluation.

Thin wrappers over `AlertStore`. Typed exceptions
(NotFoundError, DuplicateError, ValidationError) are translated into
structured `{"error": "...", "id": ...}` dicts so the MCP boundary
never raises.
"""
from __future__ import annotations

import logging
from typing import Any

from mcp_server.alerts.connection import get_alert_store
from mcp_server.alerts.store import (
    AlertError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger(__name__)


def _error(msg: str, **extra) -> dict:
    return {"error": msg, **extra}


def _handle(fn, **id_context):
    try:
        return fn()
    except DuplicateError as e:
        out = _error(str(e), **id_context)
        if e.existing_id is not None:
            out["existing_id"] = e.existing_id
        return out
    except (ValidationError, NotFoundError, AlertError) as e:
        return _error(str(e), **id_context)
    except Exception as e:
        log.exception("unexpected error")
        return _error(str(e), **id_context)


def add_alert(
    symbol: str,
    condition_type: str,
    params: dict[str, Any] | None = None,
    cooldown_seconds: int = 86400,
    status: str = "active",
) -> dict:
    """Create a new alert. See conditions.py for the supported types."""
    return _handle(
        lambda: get_alert_store().add_alert(
            symbol=symbol,
            condition_type=condition_type,
            params=params,
            cooldown_seconds=cooldown_seconds,
            status=status,
        ),
        symbol=symbol,
    )


def update_alert(
    id: str,
    symbol: str | None = None,
    condition_type: str | None = None,
    params: dict[str, Any] | None = None,
    cooldown_seconds: int | None = None,
    status: str | None = None,
) -> dict:
    """Partially update an alert. Only non-None fields are applied."""
    return _handle(
        lambda: get_alert_store().update_alert(
            id=id,
            symbol=symbol,
            condition_type=condition_type,
            params=params,
            cooldown_seconds=cooldown_seconds,
            status=status,
        ),
        id=id,
    )


def list_alerts(status: str | None = None, symbol: str | None = None) -> dict:
    """List alerts, optionally filtered by status and/or symbol."""
    try:
        rows = get_alert_store().list_alerts(status=status, symbol=symbol)
        return {"alerts": rows, "count": len(rows)}
    except (ValidationError, AlertError) as e:
        return _error(str(e))


def get_alert(id: str) -> dict:
    """Look up a single alert by id."""
    return _handle(lambda: get_alert_store().get_alert(id), id=id)


def pause_alert(id: str) -> dict:
    """Set an alert's status to 'paused'."""
    return _handle(lambda: get_alert_store().pause_alert(id), id=id)


def resume_alert(id: str) -> dict:
    """Set an alert's status to 'active'."""
    return _handle(lambda: get_alert_store().resume_alert(id), id=id)


def delete_alert(id: str, confirm: bool = False) -> dict:
    """Hard-delete an alert (fire history is preserved). Requires confirm=True."""
    if not confirm:
        return _error("delete_alert requires confirm=True to proceed", id=id)

    def _do():
        deleted = get_alert_store().delete_alert(id)
        return {"deleted": True, "id": id, "alert": deleted}

    return _handle(_do, id=id)


def get_alert_history(alert_id: str | None = None, limit: int = 50) -> dict:
    """Read recent fire records, optionally filtered to a single alert."""
    try:
        records = get_alert_store().get_alert_history(alert_id=alert_id, limit=limit)
        return {"fires": records, "count": len(records)}
    except (ValidationError, AlertError) as e:
        return _error(str(e), alert_id=alert_id)


def evaluate_alerts(symbol: str | None = None, dry_run: bool = False) -> dict:
    """Run one evaluation pass — real logic lands in Prompt 4."""
    return {
        "_stub": True,
        "evaluated": 0,
        "fired": 0,
        "suppressed_by_cooldown": 0,
        "errors": [],
        "fires": [],
        "dry_run": dry_run,
    }
