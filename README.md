# trading-bot

Tools and an MCP server for personal market analysis and paper trading.

Two parts live here:

1. **Standalone scripts** — quick Alpaca paper-trading utilities.
   - `buy_tsla.py` — submit a market-on-open buy order for TSLA.
   - `get_positions.py` — list current open positions.
2. **MCP server (`mcp_server/`)** — exposes weekly market analysis tools to
   Claude Desktop. Generates a markdown report for TSLA, BRK-B, and BTC.
   See [DESIGN.md](DESIGN.md) for the full design.

## Requirements

- Python 3.10+
- An Alpaca paper-trading account ([alpaca.markets](https://alpaca.markets))
- macOS (Claude Desktop supported on macOS and Windows)

## Setup

```bash
cd /Users/yulin/projects/trading_bot

# Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev deps
pip install -e ".[dev]"

# Configure environment variables
cp .env.example .env
# then edit .env and fill in your Alpaca paper credentials
```

Load `.env` into your shell before running scripts:

```bash
set -a && source .env && set +a
```

## Running the standalone scripts

```bash
python3 buy_tsla.py
python3 get_positions.py
```

## Running the MCP server

The server uses **stdio** transport, so it is launched by an MCP client
(Claude Desktop), not run directly. To smoke-test that the module loads:

```bash
python3 -m mcp_server.server
# (it will sit waiting for MCP messages on stdin; Ctrl-C to exit)
```

### Register with Claude Desktop

1. Open Claude Desktop's config file:
   ```bash
   open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
2. Merge the snippet from [claude_desktop_config.example.json](claude_desktop_config.example.json)
   into the `mcpServers` block. Replace the placeholder credentials with your
   real paper keys (or omit the `env` block if you've already exported them in
   the shell that launches Claude Desktop).
3. Quit Claude Desktop completely and reopen it.
4. In a new chat, the trading-bot tools should appear in the tools menu.

## Project layout

```
trading_bot/
├── buy_tsla.py
├── get_positions.py
├── DESIGN.md
├── MCP_SERVER_PROMPTS.md
├── pyproject.toml
├── claude_desktop_config.example.json
├── .env.example
└── mcp_server/
    ├── server.py            # entry point (stdio transport)
    ├── config.py            # env vars + symbol mapping
    ├── data/                # vendor API clients
    ├── analysis/            # math (RSI, SMA, vol, etc.)
    ├── report/              # markdown report assembly
    └── tools/               # MCP tool wrappers (currently stubs)
```

## Status

The MCP server is **scaffolded with stubs only** — every tool returns a
placeholder `{"_stub": True, ...}` payload. Real logic lands in subsequent
prompts (see [MCP_SERVER_PROMPTS.md](MCP_SERVER_PROMPTS.md)).
