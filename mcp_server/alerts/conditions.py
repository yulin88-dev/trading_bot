"""Canonical alert condition types with parameter schemas + validation.

Real evaluators (the part that actually fetches prices and checks fires)
land in Prompt 4. This module defines the parameter contract that
add_alert / update_alert validate against.
"""
from __future__ import annotations

from typing import Any

# Required parameters per condition_type. Keys are param names; values
# are tuples of acceptable types.
REQUIRED: dict[str, dict[str, tuple[type, ...]]] = {
    "price_above": {"target": (int, float)},
    "price_below": {"target": (int, float)},
    "price_crosses_above": {"target": (int, float)},
    "price_crosses_below": {"target": (int, float)},
    "rsi_above": {"threshold": (int, float)},
    "rsi_below": {"threshold": (int, float)},
    "sma_cross_above": {"fast": (int,), "slow": (int,)},
    "sma_cross_below": {"fast": (int,), "slow": (int,)},
    "daily_change_pct_above": {"pct": (int, float)},
    "daily_change_pct_below": {"pct": (int, float)},
    "volume_above_avg": {"multiplier": (int, float)},
    "combined_and": {"conditions": (list,)},
    "combined_or": {"conditions": (list,)},
}

# Optional parameters per condition_type.
OPTIONAL: dict[str, dict[str, tuple[type, ...]]] = {
    "rsi_above": {"period": (int,)},
    "rsi_below": {"period": (int,)},
    "volume_above_avg": {"lookback_days": (int,)},
}

# Public registry of supported condition types.
CONDITION_TYPES = frozenset(REQUIRED.keys())


class ConditionValidationError(ValueError):
    """Raised when a condition_type or its params don't validate."""


def _type_names(types: tuple[type, ...]) -> str:
    return " | ".join(t.__name__ for t in types)


def validate_condition(condition_type: str, params: dict[str, Any] | None) -> None:
    """Raise ConditionValidationError if the condition_type/params are invalid.

    Recursively validates nested conditions inside combined_and / combined_or.
    """
    if condition_type not in CONDITION_TYPES:
        raise ConditionValidationError(
            f"unknown condition_type {condition_type!r}; "
            f"must be one of {sorted(CONDITION_TYPES)}"
        )
    params = params or {}
    if not isinstance(params, dict):
        raise ConditionValidationError("params must be a dict")

    required = REQUIRED[condition_type]
    optional = OPTIONAL.get(condition_type, {})
    allowed = set(required) | set(optional)

    # Required params present + correctly typed.
    for key, types in required.items():
        if key not in params:
            raise ConditionValidationError(
                f"{condition_type} requires param {key!r}"
            )
        # bool is a subclass of int; reject silently-coerced bools.
        if isinstance(params[key], bool) or not isinstance(params[key], types):
            raise ConditionValidationError(
                f"{condition_type}.{key} must be {_type_names(types)}; "
                f"got {type(params[key]).__name__}"
            )

    # Optional params (if present) must be the right type.
    for key, types in optional.items():
        if key in params and (
            isinstance(params[key], bool) or not isinstance(params[key], types)
        ):
            raise ConditionValidationError(
                f"{condition_type}.{key} must be {_type_names(types)}; "
                f"got {type(params[key]).__name__}"
            )

    # Reject unknown params.
    extras = set(params) - allowed
    if extras:
        raise ConditionValidationError(
            f"{condition_type} does not accept params {sorted(extras)}"
        )

    # Recursively validate nested conditions for combined_*.
    if condition_type in ("combined_and", "combined_or"):
        nested = params["conditions"]
        if not nested:
            raise ConditionValidationError(
                f"{condition_type} requires at least one nested condition"
            )
        for item in nested:
            if not isinstance(item, dict):
                raise ConditionValidationError(
                    f"{condition_type} entries must be dicts; got {type(item).__name__}"
                )
            validate_condition(item.get("condition_type"), item.get("params"))
