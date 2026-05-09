"""SMTP email delivery for the v2 monitor + alert system.

Reads config from env (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/
ALERT_EMAIL_FROM/ALERT_EMAIL_TO). Connects with STARTTLS, retries once on
transient errors, supports dry_run for tests. Tools call send_digest /
send_test which both go through the same _send_message path.
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import NamedTuple

from mcp_server.notifier import templates

log = logging.getLogger(__name__)


REQUIRED_ENV = (
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "ALERT_EMAIL_FROM",
    "ALERT_EMAIL_TO",
)


# Errors worth retrying once (network/connection blips). Note: every
# smtplib.SMTPException is a subclass of OSError, so we cannot use
# OSError as a catch-all here — it would also retry SMTPAuthenticationError
# and SMTPRecipientsRefused, which are user-actionable failures.
_TRANSIENT_EXC = (
    smtplib.SMTPConnectError,
    smtplib.SMTPServerDisconnected,
    ConnectionError,   # OSError subclass: refused/reset/aborted
    TimeoutError,      # OSError subclass: socket timeout
)


class EmailConfig(NamedTuple):
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    to_addrs: list[str]


def is_configured() -> bool:
    """Return True iff every required env var is set."""
    return all(os.environ.get(k) for k in REQUIRED_ENV)


def get_config() -> EmailConfig:
    """Read and validate env vars. Raises RuntimeError if any required missing."""
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"missing env vars: {', '.join(missing)}")
    to_raw = os.environ["ALERT_EMAIL_TO"]
    return EmailConfig(
        host=os.environ["SMTP_HOST"],
        port=int(os.environ.get("SMTP_PORT", "587")),
        user=os.environ["SMTP_USER"],
        password=os.environ["SMTP_PASSWORD"],
        from_addr=os.environ["ALERT_EMAIL_FROM"],
        to_addrs=[a.strip() for a in to_raw.split(",") if a.strip()],
    )


def _send_with_retry(
    msg: EmailMessage, config: EmailConfig, max_attempts: int = 2
) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(config.user, config.password)
                smtp.send_message(msg)
            return
        except _TRANSIENT_EXC as e:
            last_exc = e
            log.warning("SMTP attempt %d/%d failed: %s", attempt, max_attempts, e)
            if attempt == max_attempts:
                break
        # All non-transient SMTP exceptions (auth, recipients refused, etc.)
        # propagate — retrying won't help.
    assert last_exc is not None
    raise last_exc


def _send_message(
    msg: EmailMessage,
    *,
    dry_run: bool = False,
    config: EmailConfig | None = None,
    to_override: list[str] | None = None,
) -> dict:
    cfg = config or get_config()
    msg["From"] = cfg.from_addr
    msg["To"] = ", ".join(to_override or cfg.to_addrs)
    rendered = msg.as_string()
    if dry_run:
        return {"sent": False, "rendered": rendered, "error": None, "dry_run": True}
    try:
        _send_with_retry(msg, cfg)
    except Exception as e:
        log.exception("SMTP send failed")
        return {"sent": False, "rendered": rendered, "error": str(e)}
    log.info(
        "email sent to=%s subject=%r",
        msg["To"],
        msg["Subject"],
    )
    return {"sent": True, "rendered": rendered, "error": None}


def send_digest(
    fires: list[dict],
    *,
    dry_run: bool = False,
    now: datetime | None = None,
    config: EmailConfig | None = None,
) -> dict:
    """Render and send a digest email for a batch of fires."""
    msg = templates.build_digest(fires, now=now)
    return _send_message(msg, dry_run=dry_run, config=config)


def send_test(
    to: str | None = None,
    body: str | None = None,
    *,
    dry_run: bool = False,
    config: EmailConfig | None = None,
) -> dict:
    """Send a hello-world message to verify SMTP setup."""
    msg = EmailMessage()
    msg["Subject"] = "[trading-bot] test email"
    msg.set_content(
        body
        or "Hello! This is a test message from trading-bot — your SMTP "
        "config is working."
    )
    to_override = [a.strip() for a in to.split(",")] if to else None
    return _send_message(msg, dry_run=dry_run, config=config, to_override=to_override)
