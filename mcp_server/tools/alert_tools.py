"""MCP tool stubs for v2 alert CRUD + evaluation.

Real CRUD lands in Prompt 3 (alert store + condition evaluators); the
delete-confirm guard already returns the canonical error so the contract
is locked in from day one.
"""
from __future__ import annotations


def add_alert(
    symbol: str,
    condition_type: str,
    params: dict | None = None,
    cooldown_seconds: int = 86400,
    status: str = "active",
) -> dict:
    """Create a new alert.

    Args:
        symbol: Asset ticker (TSLA, BRK-B, BTC, etc.).
        condition_type: One of price_above, price_below, rsi_below,
            rsi_above, sma_cross_above, sma_cross_below,
            daily_change_pct_above, daily_change_pct_below,
            volume_above_avg, combined_and, combined_or.
        params: Type-specific parameter dict (e.g., {"target": 350.0}).
        cooldown_seconds: Minimum gap between fires (default 24 h).
        status: One of active, paused, archived.
    """
    return {
        "_stub": True,
        "id": "",
        "symbol": symbol,
        "condition_type": condition_type,
        "params": params or {},
        "cooldown_seconds": cooldown_seconds,
        "status": status,
    }


def update_alert(
    id: str,
    symbol: str | None = None,
    condition_type: str | None = None,
    params: dict | None = None,
    cooldown_seconds: int | None = None,
    status: str | None = None,
) -> dict:
    """Partially update an alert. Only non-None fields are applied."""
    return {
        "_stub": True,
        "id": id,
        "updated_fields": {
            k: v
            for k, v in {
                "symbol": symbol,
                "condition_type": condition_type,
                "params": params,
                "cooldown_seconds": cooldown_seconds,
                "status": status,
            }.items()
            if v is not None
        },
    }


def list_alerts(status: str | None = None, symbol: str | None = None) -> dict:
    """List alerts, optionally filtered by status and/or symbol."""
    return {
        "_stub": True,
        "alerts": [],
        "count": 0,
        "filter": {"status": status, "symbol": symbol},
    }


def get_alert(id: str) -> dict:
    """Look up a single alert by id."""
    return {"_stub": True, "id": id}


def pause_alert(id: str) -> dict:
    """Set an alert's status to 'paused'."""
    return {"_stub": True, "id": id, "status": "paused"}


def resume_alert(id: str) -> dict:
    """Set an alert's status to 'active'."""
    return {"_stub": True, "id": id, "status": "active"}


def delete_alert(id: str, confirm: bool = False) -> dict:
    """Hard-delete an alert (fire history is preserved). Requires confirm=True."""
    if not confirm:
        return {
            "error": "delete_alert requires confirm=True to proceed",
            "id": id,
        }
    return {"_stub": True, "deleted": True, "id": id}


def get_alert_history(alert_id: str | None = None, limit: int = 50) -> dict:
    """Read recent fire records, optionally filtered to a single alert."""
    return {
        "_stub": True,
        "fires": [],
        "count": 0,
        "filter": {"alert_id": alert_id, "limit": limit},
    }


def evaluate_alerts(symbol: str | None = None, dry_run: bool = False) -> dict:
    """Run one evaluation pass across all active alerts.

    Args:
        symbol: Optional filter — only evaluate alerts on this symbol.
        dry_run: If True, do not record fires or send emails; return what
            would have happened.
    """
    return {
        "_stub": True,
        "evaluated": 0,
        "fired": 0,
        "suppressed_by_cooldown": 0,
        "errors": [],
        "fires": [],
        "dry_run": dry_run,
    }
