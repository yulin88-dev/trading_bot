"""Print a ready-to-paste Claude Desktop config block with absolute paths."""
from __future__ import annotations

import json
import os
import shutil
import sys


def main() -> None:
    python_path = shutil.which("python3") or sys.executable
    project_dir = os.path.abspath(os.getcwd())
    cfg = {
        "mcpServers": {
            "trading-bot": {
                "command": python_path,
                "args": ["-m", "mcp_server.server"],
                "cwd": project_dir,
                "env": {
                    "ALPACA_API_KEY": "your_paper_key_here",
                    "ALPACA_SECRET_KEY": "your_paper_secret_here",
                },
            }
        }
    }
    print(
        "# Add the 'trading-bot' entry below to your Claude Desktop config at:"
    )
    print(
        "# ~/Library/Application Support/Claude/claude_desktop_config.json"
    )
    print()
    print(json.dumps(cfg, indent=2))


if __name__ == "__main__":
    main()
