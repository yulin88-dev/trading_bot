# trading-bot

Tools and an MCP server for personal market analysis, paper trading, and
live alerting.

Three parts live here:

1. **Standalone scripts** — quick Alpaca paper-trading utilities.
   - `buy_tsla.py` — submit a market-on-open buy order for TSLA.
   - `get_positions.py` — list current open positions.
2. **v1 — Weekly analysis MCP server (`mcp_server/`)** — exposes data,
   analysis, and report tools to Claude Desktop. Generates a markdown
   report for **TSLA**, **BRK-B**, and **BTC** by default. See [DESIGN.md](DESIGN.md).
3. **v2 — Monitor + alerts** — entry-point alerts evaluated on a launchd
   schedule during NYSE hours, emailed via Gmail SMTP. See
   [DESIGN3.md](DESIGN3.md) and [MCP_SERVER_PROMPTS3.md](MCP_SERVER_PROMPTS3.md).

**Status:** v1 + v2 feature complete. **132 tests passing.**

## Requirements

- Python 3.10+
- An Alpaca paper-trading account ([alpaca.markets](https://alpaca.markets))
- A Gmail account with an [app password](https://myaccount.google.com/apppasswords) (for v2 alert emails)
- macOS (Claude Desktop and launchd are macOS-flavoured)

## Quickstart

```bash
make install              # installs the package + dev deps in editable mode
cp .env.example .env      # then edit .env with your Alpaca + SMTP credentials
make test                 # 132 unit tests should pass
make smoke-data           # end-to-end check of v1 data tools (live API calls)
make smoke-analysis       # end-to-end check of v1 analysis tools
make report               # generates this week's report under reports/
make monitor-dry-run      # exercise the v2 monitor without sending emails
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | `pip install -e ".[dev]"` |
| `make test` | Run the full test suite |
| `make smoke-data` | Hit Alpaca + CoinGecko + yfinance for TSLA / BRK-B / BTC |
| `make smoke-analysis` | Run all 4 v1 analysis tools end-to-end |
| `make report` | Generate `reports/weekly_report_YYYY-MM-DD.md` |
| `make run` | Launch the MCP server over stdio (for debugging) |
| `make register-help` | Print a paste-ready Claude Desktop config block |
| `make monitor-once` | Run one v2 monitor pass right now |
| `make monitor-dry-run` | Same, but record nothing and send no email |
| `make monitor-install` | Install the launchd plist |
| `make monitor-uninstall` | Remove the launchd plist |
| `make clean` | Remove caches and `reports/` |

## Environment variables

Configured via a local `.env` file (gitignored). Copy from `.env.example`.

| Variable | Required for | Purpose |
|---|---|---|
| `ALPACA_API_KEY` | v1 + v2 | Alpaca paper-trading API key |
| `ALPACA_SECRET_KEY` | v1 + v2 | Alpaca paper-trading API secret |
| `SMTP_HOST` | v2 emails | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | v2 emails | default `587` |
| `SMTP_USER` | v2 emails | full Gmail address |
| `SMTP_PASSWORD` | v2 emails | Gmail **app password** (not the account password) |
| `ALERT_EMAIL_FROM` | v2 emails | Sender address (typically same as `SMTP_USER`) |
| `ALERT_EMAIL_TO` | v2 emails | Recipient (single address or comma-separated list) |

Load into the current shell:

```bash
set -a && source .env && set +a
```

Claude Desktop launches the server with its own env block, and `monitor.py`
loads `.env` automatically via `python-dotenv`, so the manual `source` is
only needed for ad-hoc terminal invocations.

> **Alpaca data feeds:** free paper accounts only have access to the **IEX**
> feed (SIP requires a paid subscription). The server passes
> `feed=DataFeed.IEX` automatically. For symbols not in the IEX response
> (e.g., **BRK-B**), the server falls back to **yfinance** transparently.

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
3. Merge the printed `trading-bot` entry into the `mcpServers` block,
   replacing the placeholders with your real Alpaca + SMTP credentials.
4. Quit Claude Desktop completely (Cmd+Q) and reopen it.
5. In a new chat, the **trading-bot** tools should appear.

## Symbol coverage

The data and analysis tools accept **any US-listed ticker** that Alpaca or
yfinance recognizes (TSLA, AAPL, NVDA, BRK-B, …). A few symbols have explicit
mappings in [config.py](mcp_server/config.py) to handle vendor quirks:

- **BRK-B / BRK.B / BRKB** → all map to the same asset
- **BTC / BITCOIN / BTC-USD** → routed to CoinGecko (with yfinance fallback)

The `generate_weekly_report` tool defaults to **TSLA, BRK-B, BTC** but
accepts a custom `symbols` list to override.

---

# v2 — Alerts, email, and the monitor

## Adding alerts

Examples (paste into Claude Desktop):

```
Add an alert: if TSLA closes below $350 with RSI(14) under 30,
cooldown 24 h.
```

```
Add an alert: BTC daily change percent above 5%.
```

Programmatically (`Library` Python API):

```python
from mcp_server.alerts.connection import get_alert_store
store = get_alert_store()
store.add_alert(
    symbol="TSLA",
    condition_type="combined_and",
    params={
        "conditions": [
            {"condition_type": "price_below", "params": {"target": 350.0}},
            {"condition_type": "rsi_below", "params": {"threshold": 30}},
        ]
    },
    cooldown_seconds=86400,
)
```

### Supported condition types

| `condition_type` | Required params | Optional params | Fires when |
|---|---|---|---|
| `price_above` | `target` | — | latest price > target |
| `price_below` | `target` | — | latest price < target |
| `price_crosses_above` | `target` | — | prior close ≤ target < today's close |
| `price_crosses_below` | `target` | — | prior close ≥ target > today's close |
| `rsi_above` | `threshold` | `period` (default 14) | RSI > threshold |
| `rsi_below` | `threshold` | `period` (default 14) | RSI < threshold |
| `sma_cross_above` | `fast`, `slow` | — | fast SMA crosses above slow SMA today |
| `sma_cross_below` | `fast`, `slow` | — | fast SMA crosses below slow SMA today |
| `daily_change_pct_above` | `pct` | — | today's % change > pct |
| `daily_change_pct_below` | `pct` | — | today's % change < pct |
| `volume_above_avg` | `multiplier` | `lookback_days` (default 20) | today's volume > multiplier × N-day avg |
| `combined_and` | `conditions` (list) | — | every nested condition fires |
| `combined_or` | `conditions` (list) | — | at least one nested fires |

Storage: `reports/alerts/alerts.json` (the alert list) and
`reports/alerts/fires.jsonl` (append-only fire history). Both are
gitignored. `delete_alert` requires `confirm=True`. Duplicates of
`(symbol, condition_type, params)` are rejected with the existing alert's id.

## Email setup

1. Generate a Gmail **app password** at
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   (requires 2-step verification on the Gmail account).
2. Drop the values into `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=you@gmail.com
   SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ALERT_EMAIL_FROM=you@gmail.com
   ALERT_EMAIL_TO=you@gmail.com
   ```
3. Verify from Claude Desktop with the `send_test_email` tool, or directly:
   ```bash
   set -a && source .env && set +a
   python3 -c "from mcp_server.tools.notifier_tools import send_test_email; print(send_test_email())"
   ```

When the evaluator produces ≥1 fires in a single pass, the notifier sends
**one digest email** (subject lists symbols; body includes plaintext +
HTML alternatives with each fire's symbol, condition, observed value vs
threshold, and timestamp). Transient SMTP errors retry once; auth and
recipient failures do not retry.

## Scheduler setup (launchd)

```bash
make monitor-install    # writes the plist + launchctl bootstrap
make monitor-uninstall  # symmetric removal
make monitor-once       # single immediate evaluation
make monitor-dry-run    # evaluate without recording or emailing
```

The plist fires `python -m mcp_server.monitor` every **10 minutes**
(`StartInterval=600`). The script short-circuits when NYSE is closed
(uses `pandas_market_calendars` for full holiday awareness), so the extra
invocations cost almost nothing.

Logs land in `~/Library/Logs/trading-bot-monitor.log` — both stdout and
stderr from each run, including per-fire entries:
```
2026-05-09 10:31:12 [INFO] mcp_server.monitor: NYSE open ...; running evaluate_alerts(dry_run=False)
2026-05-09 10:31:14 [INFO] mcp_server.alerts.evaluator: fire alert_id=a1b2c3d4e5f6 symbol=TSLA condition=combined_and observed=... threshold=... dry_run=False
2026-05-09 10:31:15 [INFO] mcp_server.notifier.email: email sent to=you@gmail.com subject='[trading-bot] 1 alert fired: TSLA'
2026-05-09 10:31:15 [INFO] mcp_server.monitor: evaluation complete: evaluated=2 fired=1 suppressed=0 errors=0
```

To check launchd status: `launchctl print gui/$(id -u)/com.user.trading-bot-monitor`.

---

## Sample Claude Desktop prompts

Once the server is registered, paste any of these.

### v1 — analysis & reports

1. **Quick market check on any tickers**
   > Use the trading-bot tools to show me the current price and 7-day
   > performance of NVDA, AAPL, and MSFT. Format the result as a small table.

2. **Single-asset deep dive**
   > Run a full technical analysis on AMZN: RSI, SMA crossovers, MACD, and
   > 30-day volatility vs prior 30 days. Tell me whether the trend looks
   > bullish or bearish and why.

3. **Generate the weekly report (custom symbols)**
   > Generate this week's market report for TSLA, NVDA, and BTC and tell me
   > the file path. Then read the report and summarize the three biggest
   > takeaways for me.

### v2 — alerts

4. **Add an alert**
   > Alert me if TSLA closes below $350 with RSI(14) under 30, cooldown 24 h.

5. **List active alerts**
   > What alerts am I watching right now? Show their symbols, conditions,
   > and last-fired timestamps.

6. **Pause an alert**
   > Pause my BTC-above-80k alert until Monday.

7. **Test email setup**
   > Send a test alert email to confirm SMTP works.

8. **Evaluate now (dry run)**
   > Check all my alerts now and tell me which would fire — but don't
   > send any emails or record fires yet.

## Project layout

```
trading_bot/
├── buy_tsla.py
├── get_positions.py
├── DESIGN.md                # v1 design
├── DESIGN3.md               # v2 design
├── MCP_SERVER_PROMPTS.md    # v1 build-out prompts
├── MCP_SERVER_PROMPTS3.md   # v2 build-out prompts
├── Makefile
├── pyproject.toml
├── claude_desktop_config.example.json
├── .env.example
├── reports/                 # generated reports + alerts/fires (gitignored)
├── deploy/launchd/          # plist template
├── scripts/
│   ├── smoke_test_data.py
│   ├── smoke_test_analysis.py
│   ├── print_claude_config.py
│   └── render_plist.py      # produces the launchd plist with current paths
├── tests/                   # 132 tests
└── mcp_server/
    ├── server.py            # entry point (stdio); registers v1+v2 tools
    ├── monitor.py           # launchd entry point (v2)
    ├── config.py            # env vars, paths, symbol mapping
    ├── logging_setup.py     # stderr logging + log_tool decorator
    ├── data/                # vendor API clients
    ├── analysis/            # technical math (RSI, SMA, vol, benchmark)
    ├── report/              # weekly markdown report assembly
    ├── alerts/              # v2: store, conditions, evaluator, calendar
    ├── notifier/            # v2: SMTP delivery + templates
    └── tools/               # MCP tool wrappers
```
