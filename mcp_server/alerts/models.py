"""Typed dicts for v2 alert data shapes."""
from __future__ import annotations

from typing import Any, TypedDict


class Alert(TypedDict):
    id: str
    symbol: str
    condition_type: str
    params: dict[str, Any]
    status: str            # active | paused | archived
    cooldown_seconds: int
    created_at: str        # ISO 8601 UTC
    updated_at: str        # ISO 8601 UTC
    last_fired_at: str | None


class FireRecord(TypedDict):
    alert_id: str
    fired_at: str          # ISO 8601 UTC
    observed: dict[str, Any]
    message: str


class EvalResult(TypedDict):
    evaluated: int
    fired: int
    suppressed_by_cooldown: int
    errors: list[str]
    fires: list[FireRecord]
