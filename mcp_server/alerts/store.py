"""JSON-backed alert + fire-history storage.

Layout (resolved per DESIGN3.md):
- reports/alerts/alerts.json   — list of alert objects, rewritten atomically
- reports/alerts/fires.jsonl   — append-only, one JSON object per line

Real CRUD lands in Prompt 3. For now this module exposes the directory
bootstrap that server.py calls at startup so the file paths exist before
any tool is invoked.
"""
from __future__ import annotations

from pathlib import Path

from mcp_server.config import REPORTS_DIR

ALERTS_DIR = REPORTS_DIR / "alerts"
ALERTS_FILE = ALERTS_DIR / "alerts.json"
FIRES_FILE = ALERTS_DIR / "fires.jsonl"


def ensure_initialized() -> None:
    """Create the alerts directory and seed empty files if needed.

    Safe to call repeatedly — equivalent to a no-op once the structure
    exists.
    """
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ALERTS_FILE.exists():
        ALERTS_FILE.write_text("[]\n", encoding="utf-8")
    if not FIRES_FILE.exists():
        FIRES_FILE.touch()
