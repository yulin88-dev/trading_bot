"""MCP tool for weekly report generation."""
from __future__ import annotations

import logging

from mcp_server.report.generator import generate_weekly_report as _generate

log = logging.getLogger(__name__)


def generate_weekly_report(
    week_ending: str | None = None,
    symbols: list[str] | None = None,
) -> dict:
    """Build the weekly markdown report and write it to ./reports/.

    Args:
        week_ending: Optional ISO date (YYYY-MM-DD); defaults to most recent Friday.
        symbols: Optional list of tickers to include; defaults to TSLA, BRK-B, BTC.

    Returns:
        Dict with file_path (absolute), summary (one-line description),
        week_ending_date (ISO date).
    """
    try:
        return _generate(week_ending, symbols)
    except Exception as e:
        log.exception("generate_weekly_report failed")
        return {"error": str(e), "week_ending_date": week_ending}
