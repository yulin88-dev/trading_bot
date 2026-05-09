"""Render the launchd plist template with the current machine's paths.

Used by `make monitor-install`. Substitutes:
- {{python_path}}  → output of `which python3`
- {{project_dir}}  → cwd (the trading_bot repo root)
- {{log_dir}}      → $HOME/Library/Logs

Prints the rendered plist to stdout.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    template_path = Path(__file__).resolve().parent.parent / (
        "deploy/launchd/com.user.trading-bot-monitor.plist.template"
    )
    if not template_path.exists():
        sys.stderr.write(f"template not found: {template_path}\n")
        sys.exit(1)

    text = template_path.read_text(encoding="utf-8")
    rendered = (
        text
        .replace("{{python_path}}", shutil.which("python3") or sys.executable)
        .replace("{{project_dir}}", str(Path.cwd().resolve()))
        .replace("{{log_dir}}", str(Path(os.environ["HOME"]) / "Library" / "Logs"))
    )
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
