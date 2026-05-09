"""Unit tests for v2 alert CRUD — Store + tool wrappers + condition validator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.alerts.conditions import (
    ConditionValidationError,
    validate_condition,
)
from mcp_server.alerts.connection import set_alert_store
from mcp_server.alerts.store import (
    AlertStore,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from mcp_server.tools import alert_tools


@pytest.fixture
def store(tmp_path: Path) -> AlertStore:
    return AlertStore(tmp_path / "alerts")


@pytest.fixture
def store_in_tools(store: AlertStore):
    set_alert_store(store)
    yield store
    set_alert_store(None)


# ============================================================ #
# Condition validator                                          #
# ============================================================ #


class TestConditionValidator:
    def test_price_below_ok(self):
        validate_condition("price_below", {"target": 350.0})

    def test_unknown_type_rejected(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("foo", {})

    def test_missing_required_param(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("price_below", {})

    def test_wrong_type(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("price_below", {"target": "350"})

    def test_extra_param_rejected(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("price_below", {"target": 350.0, "extra": 1})

    def test_optional_param_accepted(self):
        validate_condition("rsi_below", {"threshold": 30, "period": 14})

    def test_optional_param_wrong_type(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("rsi_below", {"threshold": 30, "period": "14"})

    def test_bool_rejected_for_number(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("price_below", {"target": True})

    def test_combined_and_recursive(self):
        validate_condition(
            "combined_and",
            {
                "conditions": [
                    {"condition_type": "price_below", "params": {"target": 350.0}},
                    {"condition_type": "rsi_below", "params": {"threshold": 30}},
                ]
            },
        )

    def test_combined_empty_rejected(self):
        with pytest.raises(ConditionValidationError):
            validate_condition("combined_and", {"conditions": []})

    def test_combined_with_invalid_nested(self):
        with pytest.raises(ConditionValidationError):
            validate_condition(
                "combined_and",
                {"conditions": [{"condition_type": "price_below", "params": {}}]},
            )


# ============================================================ #
# Store — add_alert                                             #
# ============================================================ #


class TestStoreAdd:
    def test_happy_path(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        assert len(a["id"]) == 12
        assert a["symbol"] == "TSLA"
        assert a["status"] == "active"
        assert a["cooldown_seconds"] == 86400
        assert a["last_fired_at"] is None
        assert a["created_at"] == a["updated_at"]

    def test_blank_symbol_rejected(self, store):
        with pytest.raises(ValidationError):
            store.add_alert("   ", "price_below", {"target": 350})

    def test_invalid_status_rejected(self, store):
        with pytest.raises(ValidationError):
            store.add_alert("TSLA", "price_below", {"target": 350}, status="frozen")

    def test_invalid_condition_rejected(self, store):
        with pytest.raises(ValidationError):
            store.add_alert("TSLA", "bogus", {})

    def test_invalid_params_rejected(self, store):
        with pytest.raises(ValidationError):
            store.add_alert("TSLA", "price_below", {})  # missing target

    def test_negative_cooldown_rejected(self, store):
        with pytest.raises(ValidationError):
            store.add_alert(
                "TSLA", "price_below", {"target": 350}, cooldown_seconds=-1
            )

    def test_zero_cooldown_accepted(self, store):
        a = store.add_alert(
            "TSLA", "price_below", {"target": 350}, cooldown_seconds=0
        )
        assert a["cooldown_seconds"] == 0

    def test_duplicate_rejected_with_existing_id(self, store):
        first = store.add_alert("TSLA", "price_below", {"target": 350.0})
        with pytest.raises(DuplicateError) as exc_info:
            store.add_alert("TSLA", "price_below", {"target": 350.0})
        assert exc_info.value.existing_id == first["id"]

    def test_duplicate_only_on_full_match(self, store):
        store.add_alert("TSLA", "price_below", {"target": 350.0})
        # Different target → not a duplicate.
        a2 = store.add_alert("TSLA", "price_below", {"target": 360.0})
        assert a2["params"] == {"target": 360.0}


# ============================================================ #
# Store — update_alert                                          #
# ============================================================ #


class TestStoreUpdate:
    def test_partial_update(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        updated = store.update_alert(a["id"], cooldown_seconds=3600)
        assert updated["cooldown_seconds"] == 3600
        assert updated["params"] == {"target": 350.0}
        assert updated["updated_at"] >= updated["created_at"]

    def test_change_params_revalidates(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        with pytest.raises(ValidationError):
            store.update_alert(a["id"], params={})  # missing target

    def test_change_condition_type_revalidates(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        # Switch type but keep old params: now "target" isn't in rsi_below schema.
        with pytest.raises(ValidationError):
            store.update_alert(a["id"], condition_type="rsi_below")

    def test_invalid_status_rejected(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350})
        with pytest.raises(ValidationError):
            store.update_alert(a["id"], status="frozen")

    def test_not_found(self, store):
        with pytest.raises(NotFoundError):
            store.update_alert("nope", status="paused")

    def test_update_cannot_create_duplicate(self, store):
        a1 = store.add_alert("TSLA", "price_below", {"target": 350.0})
        a2 = store.add_alert("TSLA", "price_below", {"target": 360.0})
        with pytest.raises(DuplicateError) as exc:
            store.update_alert(a2["id"], params={"target": 350.0})
        assert exc.value.existing_id == a1["id"]


# ============================================================ #
# Store — list / get / pause / resume / delete                  #
# ============================================================ #


class TestStoreReadDelete:
    def test_list_filters(self, store):
        store.add_alert("TSLA", "price_below", {"target": 350})
        store.add_alert("BTC", "price_above", {"target": 80_000}, status="paused")
        assert {a["symbol"] for a in store.list_alerts(status="active")} == {"TSLA"}
        assert {a["symbol"] for a in store.list_alerts(symbol="BTC")} == {"BTC"}
        assert len(store.list_alerts()) == 2

    def test_list_invalid_status_filter(self, store):
        with pytest.raises(ValidationError):
            store.list_alerts(status="frozen")

    def test_get_by_id(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350})
        assert store.get_alert(a["id"])["symbol"] == "TSLA"

    def test_get_not_found(self, store):
        with pytest.raises(NotFoundError):
            store.get_alert("missing")

    def test_pause_and_resume(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350})
        assert store.pause_alert(a["id"])["status"] == "paused"
        assert store.resume_alert(a["id"])["status"] == "active"

    def test_delete(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350})
        deleted = store.delete_alert(a["id"])
        assert deleted["symbol"] == "TSLA"
        with pytest.raises(NotFoundError):
            store.get_alert(a["id"])

    def test_delete_not_found(self, store):
        with pytest.raises(NotFoundError):
            store.delete_alert("ghost")


# ============================================================ #
# Store — fires + history                                       #
# ============================================================ #


class TestStoreFires:
    def test_record_fire_updates_alert_and_appends(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350.0})
        record = store.record_fire(a["id"], {"price": 348.0}, "TSLA at $348")
        assert record["alert_id"] == a["id"]
        # last_fired_at on the alert is now set
        refreshed = store.get_alert(a["id"])
        assert refreshed["last_fired_at"] == record["fired_at"]
        # fires.jsonl has one line
        lines = store.fires_path.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["alert_id"] == a["id"]

    def test_history_filter_and_limit(self, store):
        a1 = store.add_alert("TSLA", "price_below", {"target": 350})
        a2 = store.add_alert("BTC", "price_above", {"target": 80_000})
        for i in range(5):
            store.record_fire(a1["id"], {"price": 350 - i}, f"fire {i}")
        store.record_fire(a2["id"], {"price": 81_000}, "btc fire")
        a1_only = store.get_alert_history(alert_id=a1["id"])
        assert all(r["alert_id"] == a1["id"] for r in a1_only)
        assert len(a1_only) == 5
        assert len(store.get_alert_history(limit=3)) == 3

    def test_history_skips_corrupt_lines(self, store):
        a = store.add_alert("TSLA", "price_below", {"target": 350})
        store.record_fire(a["id"], {"price": 349}, "ok")
        # Append a malformed line.
        with store.fires_path.open("a") as f:
            f.write("not valid json\n")
        records = store.get_alert_history()
        assert len(records) == 1


# ============================================================ #
# Atomicity                                                     #
# ============================================================ #


class TestAtomicity:
    def test_temp_file_does_not_linger(self, store):
        store.add_alert("TSLA", "price_below", {"target": 350})
        leftover = list(store.dir.glob("*.tmp"))
        assert leftover == []


# ============================================================ #
# Tool wrappers                                                 #
# ============================================================ #


class TestAlertToolWrappers:
    def test_add_returns_dict(self, store_in_tools):
        result = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        assert "error" not in result
        assert result["symbol"] == "TSLA"

    def test_add_duplicate_includes_existing_id(self, store_in_tools):
        first = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        result = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        assert "error" in result
        assert result["existing_id"] == first["id"]

    def test_add_invalid_status_returns_error(self, store_in_tools):
        result = alert_tools.add_alert(
            "TSLA", "price_below", {"target": 350}, status="frozen"
        )
        assert "error" in result

    def test_add_invalid_params_returns_error(self, store_in_tools):
        result = alert_tools.add_alert("TSLA", "price_below", {})
        assert "error" in result

    def test_get_not_found_returns_error(self, store_in_tools):
        result = alert_tools.get_alert("nope")
        assert "error" in result

    def test_delete_requires_confirm(self, store_in_tools):
        added = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        without = alert_tools.delete_alert(added["id"])
        assert "error" in without
        with_confirm = alert_tools.delete_alert(added["id"], confirm=True)
        assert with_confirm.get("deleted") is True

    def test_list_returns_count(self, store_in_tools):
        alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        alert_tools.add_alert("BTC", "price_above", {"target": 80_000})
        result = alert_tools.list_alerts()
        assert result["count"] == 2

    def test_pause_resume_via_tools(self, store_in_tools):
        added = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        assert alert_tools.pause_alert(added["id"])["status"] == "paused"
        assert alert_tools.resume_alert(added["id"])["status"] == "active"

    def test_history_via_tool(self, store_in_tools):
        added = alert_tools.add_alert("TSLA", "price_below", {"target": 350})
        store_in_tools.record_fire(added["id"], {"price": 349}, "fire")
        result = alert_tools.get_alert_history(alert_id=added["id"])
        assert result["count"] == 1
