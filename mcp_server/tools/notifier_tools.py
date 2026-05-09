"""MCP tool for SMTP notification."""
from __future__ import annotations

import logging

from mcp_server.notifier import email as email_mod

log = logging.getLogger(__name__)


def send_test_email(to: str | None = None, body: str | None = None) -> dict:
    """Send a one-line test message via the configured SMTP relay.

    Args:
        to: Recipient override (defaults to ALERT_EMAIL_TO).
        body: Optional body text override.

    Returns:
        Dict with sent (bool), rendered (the raw MIME string), error.
    """
    try:
        return email_mod.send_test(to=to, body=body)
    except RuntimeError as e:
        # Missing env vars surface as a clear, actionable error.
        return {"sent": False, "rendered": "", "error": str(e)}
    except Exception as e:
        log.exception("send_test_email failed")
        return {"sent": False, "rendered": "", "error": str(e)}
