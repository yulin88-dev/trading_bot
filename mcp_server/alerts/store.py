"""JSON-backed alert + fire-history storage.

Layout (resolved per DESIGN3.md):
- reports/alerts/alerts.json   — list of alert objects, rewritten atomically
- reports/alerts/fires.jsonl   — append-only, one JSON object per line

Concurrency note: the MCP server and the launchd monitor are separate
processes that may both touch alerts.json (the monitor writes
last_fired_at when an alert fires). Atomic temp-file rename means each
writer's snapshot is consistent, but a write-write race could lose one
side's update. Acceptable for v2 (single-user tool, narrow window);
revisit with fcntl.flock if it ever bites.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.alerts.conditions import (
    ConditionValidationError,
    validate_condition,
)
from mcp_server.config import REPORTS_DIR

ALERTS_DIR = REPORTS_DIR / "alerts"
ALERTS_FILE = ALERTS_DIR / "alerts.json"
FIRES_FILE = ALERTS_DIR / "fires.jsonl"

VALID_STATUSES = frozenset({"active", "paused", "archived"})


class AlertError(Exception):
    """Base class for typed alert-store errors."""


class NotFoundError(AlertError):
    pass


class DuplicateError(AlertError):
    def __init__(self, msg: str, existing_id: str | None = None) -> None:
        super().__init__(msg)
        self.existing_id = existing_id


class ValidationError(AlertError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def ensure_initialized(base_dir: Path | None = None) -> None:
    """Create the alerts directory and seed the empty files if needed."""
    base = Path(base_dir) if base_dir else ALERTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    alerts = base / "alerts.json"
    fires = base / "fires.jsonl"
    if not alerts.exists():
        alerts.write_text("[]\n", encoding="utf-8")
    if not fires.exists():
        fires.touch()


class AlertStore:
    """JSON-backed alert + fire-history store.

    Each call opens, mutates, and rewrites alerts.json atomically. fires.jsonl
    is append-only.
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        base = Path(base_dir).expanduser() if base_dir else ALERTS_DIR
        ensure_initialized(base)
        self.dir = base
        self.alerts_path = base / "alerts.json"
        self.fires_path = base / "fires.jsonl"

    # ------------------------------------------------------------------ #
    # JSON I/O                                                           #
    # ------------------------------------------------------------------ #

    def _load(self) -> list[dict]:
        text = self.alerts_path.read_text(encoding="utf-8")
        if not text.strip():
            return []
        return json.loads(text)

    def _save_atomic(self, alerts: list[dict]) -> None:
        tmp_path = self.alerts_path.with_name(self.alerts_path.name + ".tmp")
        tmp_path.write_text(
            json.dumps(alerts, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp_path, self.alerts_path)

    # ------------------------------------------------------------------ #
    # CRUD                                                               #
    # ------------------------------------------------------------------ #

    def add_alert(
        self,
        symbol: str,
        condition_type: str,
        params: dict[str, Any] | None = None,
        cooldown_seconds: int = 86400,
        status: str = "active",
    ) -> dict:
        symbol = (symbol or "").strip()
        if not symbol:
            raise ValidationError("symbol is required")
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}"
            )
        if (
            isinstance(cooldown_seconds, bool)
            or not isinstance(cooldown_seconds, int)
            or cooldown_seconds < 0
        ):
            raise ValidationError(
                f"cooldown_seconds must be a non-negative int; got {cooldown_seconds!r}"
            )
        try:
            validate_condition(condition_type, params)
        except ConditionValidationError as e:
            raise ValidationError(str(e)) from e

        norm_params = params or {}

        alerts = self._load()
        for existing in alerts:
            if (
                existing["symbol"] == symbol
                and existing["condition_type"] == condition_type
                and existing["params"] == norm_params
            ):
                raise DuplicateError(
                    f"duplicate alert for {symbol} / {condition_type}",
                    existing_id=existing["id"],
                )

        now = _now_iso()
        alert = {
            "id": _new_id(),
            "symbol": symbol,
            "condition_type": condition_type,
            "params": norm_params,
            "status": status,
            "cooldown_seconds": cooldown_seconds,
            "created_at": now,
            "updated_at": now,
            "last_fired_at": None,
        }
        alerts.append(alert)
        self._save_atomic(alerts)
        return alert

    def update_alert(
        self,
        id: str,
        symbol: str | None = None,
        condition_type: str | None = None,
        params: dict[str, Any] | None = None,
        cooldown_seconds: int | None = None,
        status: str | None = None,
    ) -> dict:
        alerts = self._load()
        idx = self._find_index(alerts, id)

        # Validate inputs.
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(
                f"invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}"
            )
        if cooldown_seconds is not None and (
            isinstance(cooldown_seconds, bool)
            or not isinstance(cooldown_seconds, int)
            or cooldown_seconds < 0
        ):
            raise ValidationError(
                f"cooldown_seconds must be a non-negative int; got {cooldown_seconds!r}"
            )

        # If condition_type or params changes, re-validate the (possibly
        # merged) condition spec.
        new_condition_type = (
            condition_type if condition_type is not None else alerts[idx]["condition_type"]
        )
        new_params = params if params is not None else alerts[idx]["params"]
        if condition_type is not None or params is not None:
            try:
                validate_condition(new_condition_type, new_params)
            except ConditionValidationError as e:
                raise ValidationError(str(e)) from e

        # Apply updates.
        target = alerts[idx]
        if symbol is not None:
            symbol = symbol.strip()
            if not symbol:
                raise ValidationError("symbol cannot be empty")
            target["symbol"] = symbol
        if condition_type is not None:
            target["condition_type"] = condition_type
        if params is not None:
            target["params"] = params
        if cooldown_seconds is not None:
            target["cooldown_seconds"] = cooldown_seconds
        if status is not None:
            target["status"] = status
        target["updated_at"] = _now_iso()

        # Re-check uniqueness against the other alerts.
        for i, other in enumerate(alerts):
            if i == idx:
                continue
            if (
                other["symbol"] == target["symbol"]
                and other["condition_type"] == target["condition_type"]
                and other["params"] == target["params"]
            ):
                raise DuplicateError(
                    f"duplicate alert for {target['symbol']} / {target['condition_type']}",
                    existing_id=other["id"],
                )

        self._save_atomic(alerts)
        return target

    def list_alerts(
        self, status: str | None = None, symbol: str | None = None
    ) -> list[dict]:
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(
                f"invalid status {status!r}; must be one of {sorted(VALID_STATUSES)}"
            )
        alerts = self._load()
        if status:
            alerts = [a for a in alerts if a["status"] == status]
        if symbol:
            alerts = [a for a in alerts if a["symbol"] == symbol]
        return sorted(alerts, key=lambda a: a["updated_at"], reverse=True)

    def get_alert(self, id: str) -> dict:
        alerts = self._load()
        idx = self._find_index(alerts, id)
        return alerts[idx]

    def pause_alert(self, id: str) -> dict:
        return self.update_alert(id, status="paused")

    def resume_alert(self, id: str) -> dict:
        return self.update_alert(id, status="active")

    def delete_alert(self, id: str) -> dict:
        alerts = self._load()
        idx = self._find_index(alerts, id)
        deleted = alerts.pop(idx)
        self._save_atomic(alerts)
        return deleted

    # ------------------------------------------------------------------ #
    # Fires (used by the evaluator in Prompt 4)                          #
    # ------------------------------------------------------------------ #

    def record_fire(
        self,
        alert_id: str,
        observed: dict[str, Any],
        message: str,
    ) -> dict:
        alerts = self._load()
        idx = self._find_index(alerts, alert_id)
        now = _now_iso()
        record = {
            "alert_id": alert_id,
            "fired_at": now,
            "observed": observed,
            "message": message,
        }
        # Append to fires.jsonl
        with self.fires_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        # Update the alert's last_fired_at
        alerts[idx]["last_fired_at"] = now
        alerts[idx]["updated_at"] = now
        self._save_atomic(alerts)
        return record

    def get_alert_history(
        self, alert_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        if limit < 0:
            raise ValidationError(f"limit must be non-negative; got {limit}")
        if not self.fires_path.exists():
            return []
        records: list[dict] = []
        with self.fires_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # Skip corrupt lines silently — append-only stream
                    # may have been truncated mid-write.
                    continue
                if alert_id is not None and record.get("alert_id") != alert_id:
                    continue
                records.append(record)
        # Most recent first.
        records.sort(key=lambda r: r.get("fired_at", ""), reverse=True)
        return records[:limit]

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _find_index(alerts: list[dict], id: str) -> int:
        for i, a in enumerate(alerts):
            if a["id"] == id:
                return i
        raise NotFoundError(f"alert not found: {id!r}")
