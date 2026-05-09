"""launchd entry point — runs one alert evaluation pass during NYSE hours.

Designed to be invoked every 10 min (StartInterval=600). Each invocation:
1. Loads `.env` (so launchd doesn't need the env block populated).
2. Bootstraps the alerts directory.
3. Skips early if NYSE is closed (weekend, holiday, or off-hours).
4. Otherwise calls evaluate_alerts() and logs the result.

Output goes to stdout/stderr; launchd captures both into
~/Library/Logs/trading-bot-monitor.log.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from mcp_server.alerts import store as alerts_store
from mcp_server.alerts.calendar import is_market_open
from mcp_server.alerts.evaluator import evaluate_alerts
from mcp_server.config import PROJECT_ROOT
from mcp_server.logging_setup import setup_logging

log = logging.getLogger("mcp_server.monitor")


def _load_env() -> None:
    """Load .env from the project root if it exists. Best-effort."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def main(dry_run: bool = False, now: datetime | None = None) -> int:
    _load_env()
    setup_logging()
    alerts_store.ensure_initialized()

    now = now or datetime.now(timezone.utc)
    if not is_market_open(now):
        log.info("NYSE closed at %s; skipping evaluation pass.", now.isoformat())
        return 0

    log.info("NYSE open at %s; running evaluate_alerts(dry_run=%s).",
             now.isoformat(), dry_run)
    result = evaluate_alerts(dry_run=dry_run, now=now)
    log.info(
        "evaluation complete: evaluated=%d fired=%d suppressed=%d errors=%d",
        result["evaluated"],
        result["fired"],
        result["suppressed_by_cooldown"],
        len(result["errors"]),
    )
    for err in result["errors"]:
        log.warning("eval error: %s", err)
    if result.get("email"):
        if result["email"]["sent"]:
            log.info("digest email sent")
        else:
            log.warning("digest email failed: %s", result["email"].get("error"))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="trading-bot monitor")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate alerts without recording fires or sending emails.")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
