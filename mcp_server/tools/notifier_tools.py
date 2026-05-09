"""MCP tool stub for SMTP notification. Real logic lands in Prompt 4."""
from __future__ import annotations


def send_test_email(to: str | None = None, body: str | None = None) -> dict:
    """Send a one-line test message via the configured SMTP relay.

    Args:
        to: Recipient override (defaults to ALERT_EMAIL_TO).
        body: Optional body text override.

    Returns:
        Dict with sent (bool), rendered (the raw MIME message), error.
    """
    return {
        "_stub": True,
        "sent": False,
        "rendered": "",
        "error": "not implemented (lands in Prompt 4)",
    }
