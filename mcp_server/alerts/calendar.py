"""NYSE market-hours check.

Isolated behind `is_market_open()` so the implementation can be swapped
(hand-rolled weekday check ↔ pandas_market_calendars ↔ exchange API)
without touching the monitor entry point.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_nyse: Any | None = None


def _calendar() -> Any:
    """Lazy-init the NYSE calendar from pandas_market_calendars."""
    global _nyse
    if _nyse is None:
        import pandas_market_calendars as mcal

        _nyse = mcal.get_calendar("NYSE")
    return _nyse


def is_market_open(now: datetime | None = None) -> bool:
    """True if NYSE is open at `now` (default: real time, in UTC)."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    # `schedule` takes ET dates; the returned market_open / market_close
    # timestamps are tz-aware UTC.
    from zoneinfo import ZoneInfo

    et_date = now_utc.astimezone(ZoneInfo("America/New_York")).date()
    schedule = _calendar().schedule(start_date=et_date, end_date=et_date)
    if schedule.empty:
        return False
    market_open = schedule.iloc[0]["market_open"].to_pydatetime()
    market_close = schedule.iloc[0]["market_close"].to_pydatetime()
    return market_open <= now_utc <= market_close
