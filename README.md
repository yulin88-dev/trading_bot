# trading-bot

Tools and an MCP server for personal market analysis and paper trading.

Two parts live here:

1. **Standalone scripts** — quick Alpaca paper-trading utilities.
   - `buy_tsla.py` — submit a market-on-open buy order for TSLA.
   - `get_positions.py` — list current open positions.
2. **MCP server (`mcp_server/`)** — exposes weekly market analysis tools to
   Claude Desktop. Generates a markdown report for **TSLA**, **BRK-B**, and
   **BTC**. See [DESIGN.md](DESIGN.md) for the full design.

## Requirements

- Python 3.10+
- An Alpaca paper-trading account ([alpaca.markets](https://alpaca.markets))
- macOS (Claude Desktop is supported on macOS and Windows)

## Quickstart

```bash
make install         # installs the package + dev deps in editable mode
cp .env.example .env # then edit .env with your Alpaca paper credentials
make test            # 17 unit tests should pass
make smoke-data      # end-to-end check of data tools (live API calls)
make smoke-analysis  # end-to-end check of analysis tools
make report          # generates this week's report under reports/
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | `pip install -e ".[dev]"` |
| `make test` | Run the unit tests in `tests/` |
| `make smoke-data` | Hit Alpaca + CoinGecko + yfinance for TSLA / BRK-B / BTC |
| `make smoke-analysis` | Run all 4 analysis tools end-to-end |
| `make report` | Generate `reports/weekly_report_YYYY-MM-DD.md` |
| `make run` | Launch the MCP server over stdio (for debugging) |
| `make register-help` | Print a ready-to-paste Claude Desktop config block |
| `make clean` | Remove caches and `reports/` |

## Environment variables

Configured via a local `.env` file (gitignored). Copy from `.env.example`:

| Variable | Required | Purpose |
|---|---|---|
| `ALPACA_API_KEY` | yes | Alpaca paper-trading API key |
| `ALPACA_SECRET_KEY` | yes | Alpaca paper-trading API secret |

Load `.env` into your shell before running scripts directly:

```bash
set -a && source .env && set +a
```

Claude Desktop launches the server with its own env block, so the `.env`
file is only needed when running scripts manually from the terminal.

> **Note on Alpaca data feeds:** free Alpaca paper accounts only have
> access to the **IEX** feed (SIP requires a paid subscription). The
> server passes `feed=DataFeed.IEX` automatically. For symbols not in the
> IEX response (e.g., **BRK-B** at the time of writing), the server falls
> back to **yfinance** transparently.

## Running the standalone scripts

```bash
python3 buy_tsla.py
python3 get_positions.py
```

## Registering the MCP server with Claude Desktop

The server uses **stdio** transport — Claude Desktop launches it on demand.

1. Generate a config block with absolute paths:
   ```bash
   make register-help
   ```
2. Open the Claude Desktop config:
   ```bash
   open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
3. Merge the printed `trading-bot` entry into the `mcpServers` block, replacing
   the placeholder credentials with your real Alpaca paper keys.
4. Quit Claude Desktop completely (Cmd+Q) and reopen it.
5. In a new chat, the **trading-bot** tools should appear in the tools menu.

## Sample Claude Desktop prompts

Once the server is registered, paste any of these into a Claude Desktop chat
to exercise the full pipeline:

1. **Quick market check**
   > Use the trading-bot tools to show me the current price and 7-day
   > performance of TSLA, BRK-B, and BTC. Format the result as a small table.

2. **Single-asset deep dive**
   > Run a full technical analysis on BTC: RSI, SMA crossovers, MACD, and
   > 30-day volatility vs prior 30 days. Tell me whether the trend looks
   > bullish or bearish and why.

3. **Generate the weekly report**
   > Generate this week's market report and tell me the file path. Then read
   > the report and summarize the three biggest takeaways for me.

## Project layout

```
trading_bot/
├── buy_tsla.py
├── get_positions.py
├── DESIGN.md
├── MCP_SERVER_PROMPTS.md
├── Makefile
├── pyproject.toml
├── claude_desktop_config.example.json
├── .env.example
├── reports/                 # generated reports (gitignored)
├── scripts/
│   ├── smoke_test_data.py
│   ├── smoke_test_analysis.py
│   └── print_claude_config.py
├── tests/
│   └── test_analysis.py     # 17 unit tests for the math
└── mcp_server/
    ├── server.py            # entry point (stdio transport)
    ├── config.py            # env vars, paths, symbol mapping
    ├── logging_setup.py     # stderr logging + per-tool tracing
    ├── data/                # vendor API clients (Alpaca, CoinGecko, yfinance)
    ├── analysis/            # math (RSI, SMA, vol, benchmark)
    ├── report/              # markdown report assembly
    └── tools/               # MCP tool wrappers
```
