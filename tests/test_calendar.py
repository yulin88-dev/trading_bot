"""Unit tests for the NYSE market-hours check."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from mcp_server.alerts.calendar import is_market_open


def _et(year, month, day, hour, minute=0):
    """Build a tz-aware datetime in America/New_York."""
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


class TestIsMarketOpen:
    def test_open_during_session(self):
        # Friday 2026-05-08 at 10:30 ET — middle of the session.
        assert is_market_open(_et(2026, 5, 8, 10, 30)) is True

    def test_closed_before_open(self):
        # Friday 2026-05-08 at 9:00 ET — before 9:30 open.
        assert is_market_open(_et(2026, 5, 8, 9, 0)) is False

    def test_closed_after_close(self):
        # Friday 2026-05-08 at 16:30 ET — after 16:00 close.
        assert is_market_open(_et(2026, 5, 8, 16, 30)) is False

    def test_closed_on_saturday(self):
        # Saturday 2026-05-09 at 10:30 ET — markets closed weekends.
        assert is_market_open(_et(2026, 5, 9, 10, 30)) is False

    def test_closed_on_sunday(self):
        assert is_market_open(_et(2026, 5, 10, 10, 30)) is False

    def test_closed_on_us_holiday_independence_day(self):
        # 2026-07-03 is the observed July 4 holiday (Saturday actual → Friday observed).
        # NYSE closes on the observed holiday.
        assert is_market_open(_et(2026, 7, 3, 11, 0)) is False

    def test_accepts_utc_input(self):
        # 14:30 UTC on 2026-05-08 == 10:30 ET (DST in effect, UTC-4).
        utc = datetime(2026, 5, 8, 14, 30, tzinfo=timezone.utc)
        assert is_market_open(utc) is True

    def test_naive_input_assumed_utc(self):
        # Naive datetime treated as UTC. 21:00 naive == 21:00 UTC == 17:00 ET (post-close).
        naive = datetime(2026, 5, 8, 21, 0)
        assert is_market_open(naive) is False
