"""launchd entry point for the monitor + alert evaluation loop.

Real implementation lands in Prompt 5 (NYSE-hours check via
pandas_market_calendars + evaluate_alerts dispatch). For now this is a
stub that logs and exits 0.
"""
from __future__ import annotations

import logging
import sys

from mcp_server.alerts import store as alerts_store
from mcp_server.logging_setup import setup_logging

log = logging.getLogger("mcp_server.monitor")


def main(dry_run: bool = False) -> int:
    setup_logging()
    alerts_store.ensure_initialized()
    log.info("monitor stub invoked (dry_run=%s) — Prompt 5 will fill this in", dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
