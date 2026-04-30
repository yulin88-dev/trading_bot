"""Smoke test for the data tools.

Run after `pip install -e ".[dev]"` and exporting Alpaca credentials:

    set -a && source .env && set +a
    python3 scripts/smoke_test_data.py
"""
from __future__ import annotations

import json
import sys

from mcp_server.tools.data_tools import (
    get_current_quote,
    get_news,
    get_price_history,
)

SYMBOLS = ["TSLA", "BRK-B", "BTC"]


def _heading(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def main() -> int:
    failures = 0

    for sym in SYMBOLS:
        _heading(f"get_price_history({sym!r}, days=7)")
        result = get_price_history(sym, days=7)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1
        elif not result.get("bars"):
            print(f"WARN: no bars returned for {sym}")

    for sym in SYMBOLS:
        _heading(f"get_current_quote({sym!r})")
        result = get_current_quote(sym)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    for sym in SYMBOLS:
        _heading(f"get_news({sym!r}, days=3)")
        result = get_news(sym, days=3)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    _heading(f"Summary: {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
