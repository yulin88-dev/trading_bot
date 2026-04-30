# MCP Server — Weekly Market Analysis Prompts

A structured set of prompts to incrementally build an MCP server that performs
weekly market analysis and generates reports for **TSLA**, **BRK-B**, and **BTC**.

## Decisions to make first

Fill these in before using the prompts below:

- **Data sources**: Alpaca (paper account) + yfinance for stocks; CoinGecko or Coinbase for BTC
- **Report format**: Markdown / PDF / HTML email
- **Delivery**: Saved file / email / Slack
- **Client**: Claude Desktop / Claude Code
- **Schedule**: Manual trigger or auto (e.g., Friday 4pm ET)

---

## Prompt 1 — Architecture & design

```
I want to build an MCP (Model Context Protocol) server that performs weekly
market analysis and generates a report for three assets: TSLA (Tesla),
BRK-B (Berkshire Hathaway Class B), and BTC (Bitcoin).

Goals:
- Expose MCP tools that fetch price data, compute analysis, and generate the
  weekly report.
- Run locally on macOS, used from Claude Desktop.
- Data sources: Alpaca for stocks (paper account), CoinGecko for BTC, and
  yfinance as a fallback.
- Report output: Markdown file saved to ./reports/ with filename
  weekly_report_YYYY-MM-DD.md.

Please propose:
1. The MCP server's directory structure and module layout.
2. The exact list of MCP tools to expose (name, inputs, outputs, purpose).
3. The data flow — which tool calls which data source.
4. The report template (sections + what each section contains).
5. Dependencies (Python packages) and a minimal pyproject.toml or
   requirements.txt.

Do not write code yet. I want a design doc first.
```

---

## Prompt 2 — MCP server skeleton

```
Using the design we agreed on, scaffold the MCP server in Python using the
`mcp` SDK (https://github.com/modelcontextprotocol/python-sdk).

Requirements:
- Use stdio transport (for Claude Desktop integration).
- Project layout matches the design doc.
- Include a working `server.py` with the server initialized and an empty
  list of tools registered.
- Include a `claude_desktop_config.json` snippet showing how to add this
  server to Claude Desktop's config.
- Include a README with setup steps (venv, install, register, run).

Do not implement tool logic yet — just the skeleton with stubs that return
placeholder data.
```

---

## Prompt 3 — Market data tools

```
Implement these MCP tools in the server:

1. get_price_history(symbol, days) — returns OHLCV daily bars.
   - TSLA, BRKB → Alpaca historical bars API (paper credentials from env).
   - BTC → CoinGecko /coins/bitcoin/market_chart endpoint.
2. get_current_quote(symbol) — returns latest price, daily change, volume.
3. get_news(symbol, days) — returns headlines from the last N days.
   - Use Alpaca news API for stocks; for BTC, use CoinGecko or NewsAPI.

Constraints:
- All API keys read from environment variables (ALPACA_API_KEY,
  ALPACA_SECRET_KEY, NEWSAPI_KEY).
- Handle the symbol mapping: "BRK-B" / "BRK.B" / "BRKB" — Alpaca expects "BRKB".
- Return structured data (typed dicts), not raw API JSON.
- Include error handling for rate limits and missing data — return clear
  error messages, do not crash the server.

Show me the final code for each tool plus a short test script that calls
each one and prints the output.
```

---

## Prompt 4 — Analysis tools

```
Add these analysis MCP tools:

1. compute_weekly_performance(symbol) — % change over the past 7 days,
   high, low, average volume, and comparison vs. the prior week.
2. compute_technicals(symbol) — RSI(14), 20-day SMA, 50-day SMA, MACD,
   and current position relative to each.
3. compute_volatility(symbol) — 30-day annualized volatility and a
   week-over-week volatility delta.
4. compare_to_benchmark(symbol, benchmark) — relative performance vs.
   SPY (for stocks) or BTC's correlation to SPY (for crypto).

Use pandas + numpy for the math. Each tool returns a structured dict
that the report generator can format directly. Include unit tests for
the math (use known inputs with hand-calculated outputs).
```

---

## Prompt 5 — Report generator

```
Add an MCP tool `generate_weekly_report()` that produces a markdown
report with this structure:

# Weekly Market Report — {week_ending_date}

## Executive Summary
3–5 bullet points on the week's key moves across TSLA, BRKB, BTC.

## Per-Asset Sections (one per asset)
- Performance table (price, weekly %, YTD %, volume).
- Technical signals (RSI, SMA crossovers, MACD).
- Volatility commentary.
- Top 3 news headlines with date and source link.
- One-paragraph plain-English assessment.

## Cross-Asset Comparison
Table comparing the three assets on weekly return, volatility, and
correlation to SPY.

## Outlook & Watch Items
List of upcoming earnings dates, macro events, and notable technical
levels to watch.

The tool should:
- Pull data via the existing tools (no duplicated API logic).
- Save the file to ./reports/weekly_report_YYYY-MM-DD.md.
- Return the file path and a short summary string.

Show me both the implementation and a sample rendered report using
last week's data.
```

---

## Prompt 6 — Polish & deploy

```
Final pass on the MCP server:

1. Add structured logging (which tool was called, with what args, how long
   it took, success/failure).
2. Add a `.env.example` and document env vars in README.
3. Add a `make` target or shell script for: install, test, run, and
   register-with-claude-desktop.
4. Show me the exact Claude Desktop config block with absolute paths.
5. Provide three sample chat prompts I can paste into Claude Desktop to
   test the server end-to-end.
```

---

## How to use these prompts

Run the prompts one at a time in a fresh session. Paste the output of the
previous prompt as context into the next one so each step builds on the last.
