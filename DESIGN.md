# MCP Server — Weekly Market Analysis (Design Doc)

**Status:** Draft — output of Prompt 1
**Scope:** Local MCP server (stdio) for Claude Desktop. Generates a weekly markdown report for **TSLA**, **BRK-B**, and **BTC**.

---

## 1. Directory structure

```
trading_bot/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                # MCP server entry point + tool registration
│   ├── config.py                # env vars, symbol mapping, constants
│   ├── data/
│   │   ├── __init__.py
│   │   ├── alpaca_client.py     # Alpaca: bars, quotes, news (TSLA, BRKB)
│   │   ├── coingecko_client.py  # CoinGecko: BTC price + news
│   │   ├── yfinance_client.py   # yfinance fallback (all symbols)
│   │   └── models.py            # typed dicts / dataclasses for return shapes
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── performance.py       # weekly perf, YTD, volume aggregates
│   │   ├── technicals.py        # RSI, SMA, MACD
│   │   ├── volatility.py        # rolling annualized vol, week-over-week delta
│   │   └── benchmark.py         # SPY comparison, correlation
│   ├── report/
│   │   ├── __init__.py
│   │   ├── generator.py         # orchestrates analysis + writes file
│   │   └── templates.py         # section-level markdown templates
│   └── tools/
│       ├── __init__.py
│       ├── data_tools.py        # MCP wrappers for data fetching
│       ├── analysis_tools.py    # MCP wrappers for analysis
│       └── report_tools.py      # MCP wrapper for report generation
├── reports/                     # output dir (gitignored)
├── tests/
│   ├── test_analysis.py
│   ├── test_data_clients.py
│   └── test_report.py
├── .env.example
├── pyproject.toml
├── claude_desktop_config.example.json
└── README.md
```

**Layering rule:** `tools/` → `analysis/` and `report/` → `data/`. Tools are thin MCP adapters; never call vendor SDKs directly.

---

## 2. MCP tools to expose

### Data tools

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `get_price_history` | `symbol: str`, `days: int = 30` | List of OHLCV bars `{date, open, high, low, close, volume}` | Daily bars from primary source with fallback. |
| `get_current_quote` | `symbol: str` | `{price, change_pct, volume, as_of}` | Latest snapshot quote. |
| `get_news` | `symbol: str`, `days: int = 7` | List of `{date, title, source, url, summary}` | Headlines for the past N days. |

### Analysis tools

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `compute_weekly_performance` | `symbol: str` | `{weekly_return_pct, week_high, week_low, avg_volume, prior_week_return_pct, delta_pp}` | Past 7d vs prior 7d. |
| `compute_technicals` | `symbol: str` | `{rsi_14, sma_20, sma_50, macd_line, macd_signal, macd_hist, price_vs_sma20, price_vs_sma50, crossover_signal}` | Standard technicals. |
| `compute_volatility` | `symbol: str` | `{ann_vol_30d, ann_vol_prior_30d, vol_delta_pct}` | Annualized realized vol + WoW delta. |
| `compare_to_benchmark` | `symbol: str`, `benchmark: str = "SPY"` | `{symbol_return_pct, benchmark_return_pct, alpha, correlation_30d}` | Relative performance + correlation. |

### Report tool

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `generate_weekly_report` | `week_ending: str \| None = None` | `{file_path, summary, week_ending_date}` | Builds and writes the full report. |

**Total: 8 MCP tools.**

---

## 3. Data flow

| Tool | TSLA / BRKB | BTC |
|---|---|---|
| `get_price_history` | Alpaca `/v2/stocks/{symbol}/bars` → yfinance fallback | CoinGecko `/coins/bitcoin/market_chart` → yfinance `BTC-USD` fallback |
| `get_current_quote` | Alpaca `/v2/stocks/{symbol}/snapshot` | CoinGecko `/simple/price` |
| `get_news` | Alpaca `/v1beta1/news` | _skipped in v1 — returns empty list_ |
| `compute_*` (analysis) | Calls `get_price_history` internally — no direct vendor calls | Same |
| `compare_to_benchmark` | Loads `symbol` + `SPY` via `get_price_history` | Same; for BTC, correlation is BTC vs SPY |
| `generate_weekly_report` | Orchestrates all tools above for each of the 3 assets | Same |

**Symbol normalization** (in `config.py`):

| User input | Alpaca | yfinance | CoinGecko |
|---|---|---|---|
| `TSLA`, `tsla` | `TSLA` | `TSLA` | — |
| `BRK-B`, `BRK.B`, `BRKB` | `BRKB` | `BRK-B` | — |
| `BTC`, `BITCOIN`, `btc-usd` | — | `BTC-USD` | `bitcoin` |
| `SPY` | `SPY` | `SPY` | — |

---

## 4. Report template

```markdown
# Weekly Market Report — {week_ending_date}

## Executive Summary
- {3–5 bullets on the week's biggest moves across the 3 assets}

---

## TSLA — Tesla, Inc.

### Performance
| Metric        | Value         |
|---------------|---------------|
| Close         | ${close}      |
| Weekly Return | {weekly_pct}% |
| YTD Return    | {ytd_pct}%    |
| Avg Volume    | {avg_vol}     |

### Technical Signals
- RSI (14): {rsi} ({overbought/oversold/neutral})
- 20-day SMA: ${sma20} (price is {above/below})
- 50-day SMA: ${sma50} (price is {above/below})
- MACD: {bullish/bearish}, histogram {expanding/contracting}

### Volatility
{one-paragraph commentary referencing 30d vol and WoW delta}

### Top News
1. [{title}]({url}) — {source}, {date}
2. ...
3. ...

### Assessment
{one paragraph plain-English read on the week — combines perf + technicals + news}

---

## BRK-B — Berkshire Hathaway Class B
{same structure}

---

## BTC — Bitcoin
{same structure, plus BTC-specific notes (correlation regime, on-chain news)}

---

## Cross-Asset Comparison

| Asset | Weekly Return | 30d Ann. Vol | Corr to SPY |
|-------|---------------|--------------|-------------|
| TSLA  | ...           | ...          | ...         |
| BRK-B | ...           | ...          | ...         |
| BTC   | ...           | ...          | ...         |

## Outlook & Watch Items
- **Earnings:** {upcoming dates for TSLA/BRK-B}
- **Macro events:** {Fed meetings, CPI prints, etc.}
- **Technical levels:** {support/resistance per asset}
```

---

## 5. Dependencies

`pyproject.toml`:

```toml
[project]
name = "trading-bot-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "alpaca-py>=0.30.0",
    "yfinance>=0.2.40",
    "requests>=2.31.0",
    "pandas>=2.2.0",
    "numpy>=1.26.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.5.0",
]

[project.scripts]
trading-bot-mcp = "mcp_server.server:main"
```

Or `requirements.txt`:

```
mcp>=1.0.0
alpaca-py>=0.30.0
yfinance>=0.2.40
requests>=2.31.0
pandas>=2.2.0
numpy>=1.26.0
python-dotenv>=1.0.0
```

**Required environment variables:**
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` — paper account credentials

---

## Open questions / decisions before Prompt 2

1. **News for BTC:** skip BTC news in v1
2. **YTD calculation:** based on calendar year start
3. **Report file collisions:** if `weekly_report_2026-04-26.md` already exists, overwrite
4. **Tests:** hit Alpaca paper endpoints in CI? yes

Resolve these before scaffolding.
