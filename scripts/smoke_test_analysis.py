"""Smoke test for the analysis tools — runs against live data."""
from __future__ import annotations

import json
import sys

from mcp_server.tools.analysis_tools import (
    compare_to_benchmark,
    compute_technicals,
    compute_volatility,
    compute_weekly_performance,
)

SYMBOLS = ["TSLA", "BRK-B", "BTC"]


def _heading(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def main() -> int:
    failures = 0

    for sym in SYMBOLS:
        _heading(f"compute_weekly_performance({sym!r})")
        result = compute_weekly_performance(sym)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    for sym in SYMBOLS:
        _heading(f"compute_technicals({sym!r})")
        result = compute_technicals(sym)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    for sym in SYMBOLS:
        _heading(f"compute_volatility({sym!r})")
        result = compute_volatility(sym)
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    for sym in SYMBOLS:
        _heading(f"compare_to_benchmark({sym!r}, 'SPY')")
        result = compare_to_benchmark(sym, "SPY")
        print(json.dumps(result, indent=2, default=str))
        if "error" in result:
            failures += 1

    _heading(f"Summary: {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
