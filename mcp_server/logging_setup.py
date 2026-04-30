"""Logging setup for the MCP server.

stdout is reserved for the MCP protocol over stdio, so all logs MUST go to
stderr. The `log_tool` decorator records each tool invocation with args,
duration, and success/failure.
"""
from __future__ import annotations

import logging
import sys
import time
from functools import wraps
from typing import Any, Callable

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Route logs to stderr (stdout is the MCP protocol channel)."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def log_tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a tool function to log entry, duration, and result status."""
    log = logging.getLogger("mcp_server.tools")

    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        arg_pieces = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
        args_str = ", ".join(arg_pieces)
        log.info("call %s(%s)", fn.__name__, args_str)
        try:
            result = fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            status = "error" if isinstance(result, dict) and "error" in result else "ok"
            log.info("done %s status=%s duration_ms=%.0f", fn.__name__, status, duration_ms)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            log.exception(
                "fail %s duration_ms=%.0f error=%r", fn.__name__, duration_ms, e
            )
            raise

    return wrapper
