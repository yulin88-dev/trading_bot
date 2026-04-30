"""MCP tool stub for report generation. Real logic lands in Prompt 5."""
from __future__ import annotations


def generate_weekly_report(week_ending: str | None = None) -> dict:
    """Build the weekly markdown report and write it to ./reports/.

    Args:
        week_ending: Optional ISO date (YYYY-MM-DD); defaults to most recent Friday.

    Returns:
        Dict with file_path, summary, week_ending_date.
    """
    return {
        "_stub": True,
        "file_path": None,
        "summary": "Stub — report generation not implemented yet.",
        "week_ending_date": week_ending,
    }
