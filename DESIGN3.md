# Trading Bot v2 — Monitor & Alert (Design Doc)

**Status:** Draft — output of Prompt 1 in [MCP_SERVER_PROMPTS3.md](MCP_SERVER_PROMPTS3.md)
**Scope:** Extend the existing trading-bot MCP server with entry-point alerts, evaluated on a launchd schedule and emailed to me via Gmail SMTP (stdlib `smtplib`). Reuses every v1 data tool; adds 10 new MCP tools.

---

## 1. Architecture — extend, don't fork

**Recommendation:** extend the existing `mcp_server/` package in-place.

Reasoning vs creating a sibling package:

| Concern | Extend (chosen) | Sibling package |
|---|---|---|
| Reuse of v1 data tools | Free — direct import | Requires shipping v1 as a library or duplicating code |
| Deployment | One Python install, one Claude Desktop entry, one Makefile | Two installs, two server entries, two Makefiles |
| Blast radius if v2 has a bug | Risk to v1 only if shared modules are touched (data, analysis, normalize_symbol) — those don't change | None on v1 |
| Conceptual clarity | "trading-bot" covers both reporting and alerting | Cleaner separation but more friction for a one-user tool |

**New modules**, alongside the existing v1 layout:

```
trading_bot/
└── mcp_server/
    ├── server.py                    # registers v1 + v2 tools
    ├── alerts/
    │   ├── __init__.py
    │   ├── store.py                 # JSON-backed CRUD for alerts + fire history
    │   ├── conditions.py            # canonical condition evaluators (Prompt 3)
    │   ├── evaluator.py             # evaluate_alerts orchestration (Prompt 3)
    │   └── models.py                # TypedDicts: Alert, FireRecord, EvalResult
    ├── notifier/
    │   ├── __init__.py
    │   ├── email.py                 # smtplib wrapper, dry-run support (Prompt 4)
    │   └── templates.py             # subject + body renderers
    ├── monitor.py                   # launchd entry point (Prompt 5)
    └── tools/
        ├── alert_tools.py           # MCP wrappers for CRUD + evaluate_alerts
        └── notifier_tools.py        # MCP wrapper for send_test_email
```

**Layering rule:** `tools/` → `alerts/`+`notifier/` → `data/`+`analysis/`. The new evaluator never calls vendor APIs directly — it goes through the existing `get_current_quote` / `get_price_history` / `compute_technicals` tools so caching and fallback chains are inherited automatically.

---

## 2. Alert schema — JSON files in `reports/alerts/`

Per the storage decision, alerts live in JSON files under the existing `reports/` tree:

```
reports/
└── alerts/
    ├── alerts.json     # list of alert objects (mutable; rewritten via temp-file rename)
    └── fires.jsonl     # append-only fire history, one JSON object per line
```

**Atomicity:** every write to `alerts.json` writes to `alerts.json.tmp` first, then `os.replace()`s it into place. POSIX guarantees the rename is atomic, so readers always see either the old or new file, never a partial write.

**Alert object:**

```json
{
  "id": "a1b2c3d4e5f6",
  "symbol": "TSLA",
  "condition_type": "combined_and",
  "params": {
    "conditions": [
      {"condition_type": "price_below", "params": {"target": 350.0}},
      {"condition_type": "rsi_below",   "params": {"threshold": 30, "period": 14}}
    ]
  },
  "status": "active",
  "cooldown_seconds": 86400,
  "created_at": "2026-05-04T17:32:11Z",
  "updated_at": "2026-05-04T17:32:11Z",
  "last_fired_at": null
}
```

**Fire record (one line per fire):**

```json
{"alert_id": "a1b2c3d4e5f6", "fired_at": "2026-05-05T14:35:00Z", "observed": {"price": 348.50, "rsi_14": 28.4}, "message": "TSLA at $348.50 below $350; RSI(14) at 28.4 below 30."}
```

**ID format:** `uuid.uuid4().hex[:12]` — 12-char short UUIDs. Easy to distinguish in logs without colliding.

**Status whitelist:** `{active, paused, archived}`. Validated on add and update.

---

## 3. MCP tools to expose

### Alert CRUD (8)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `add_alert` | `symbol`, `condition_type`, `params`, `cooldown_seconds=86400`, `status='active'` | New alert dict | Create. params validated against the condition schema. |
| `update_alert` | `id`, `**fields` | Updated alert dict | Partial update. |
| `list_alerts` | `status?`, `symbol?` | List of alerts | Filter. |
| `get_alert` | `id` | Alert dict | Read one. |
| `pause_alert` | `id` | Updated dict | `status='paused'`. |
| `resume_alert` | `id` | Updated dict | `status='active'`. |
| `delete_alert` | `id`, `confirm=False` | `{deleted: true, id}` | Hard delete; cascades fires? No — fires are kept for audit. Requires `confirm=True`. |
| `get_alert_history` | `alert_id?`, `limit=50` | List of fire records | Read fires.jsonl, optionally filtered. |

### Evaluation (1)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `evaluate_alerts` | `symbol?`, `dry_run=False` | `{evaluated, fired, suppressed_by_cooldown, errors, fires: [...]}` | One-pass evaluation. Used by both the launchd monitor and on-demand from Claude Desktop. |

### Notification (1)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `send_test_email` | `to?`, `body?` | `{sent, rendered, error}` | Verify the SMTP config is working. |

**Total: 10 new tools** (18 total when added to v1's 8).

---

## 4. Data flow

```
Claude Desktop / launchd
         │
         │  MCP stdio (Claude Desktop)        Subprocess invocation (launchd)
         ▼                                    ▼
mcp_server/server.py                   mcp_server/monitor.py
         │                                    │
         │  (CRUD, send_test_email)           │  determines NYSE-open;
         │  (evaluate_alerts on-demand)       │  calls evaluate_alerts(...)
         ▼                                    ▼
mcp_server/tools/alert_tools.py    ◄─────────┘
         │
         │  validates params, normalizes symbols
         ▼
mcp_server/alerts/evaluator.py
         │
         │  loads active alerts from store
         │  for each: dispatch to mcp_server/alerts/conditions.py
         ▼
data tools  (get_current_quote, get_price_history, compute_technicals)
         │
         │  pulls cached/fresh prices via v1's vendor fallback chain
         ▼
mcp_server/alerts/store.py    ──►   reports/alerts/alerts.json + fires.jsonl
         │
         │  for each fire: respect cooldown, append to fires.jsonl
         ▼
mcp_server/notifier/email.py  ──►   smtplib → SMTP_HOST:SMTP_PORT
```

A single per-symbol quote cache lives inside `evaluate_alerts` so two alerts on TSLA share one quote fetch.

---

## 5. Scheduler design — launchd, every 10 minutes during NYSE hours

**Plist:** `deploy/launchd/com.user.trading-bot-monitor.plist`, with a `StartCalendarInterval` array covering `9:30, 9:40, ..., 15:50` on `Weekday: 1..5` (`Weekday: 0` is Sunday in launchd; Mon..Fri is 1..5).

**`monitor.py` entry point:**
1. Load `pandas_market_calendars` for NYSE; check whether _today_ is a trading day (skip US holidays even when launchd fires).
2. If NYSE is closed (holiday or off-hours), exit early without evaluating any alerts (stocks _and_ BTC, per the resolved decision below).
3. Otherwise call `evaluate_alerts()` and exit.
4. Logs go to stderr → captured to `~/Library/Logs/trading-bot-monitor.log` via `StandardErrorPath`.

> **Decision:** BTC alerts are also evaluated only during NYSE hours (single plist, weekdays 9:30–16:00 ET). The "BTC 24/7" goal from Prompt 1 is dropped for v2 in favor of operational simplicity. Revisit by adding a second crypto-only plist if alerts feel too laggy.

**Make targets** (added to existing Makefile):

| Target | What it does |
|---|---|
| `make monitor-install` | `launchctl bootstrap gui/$(id -u) deploy/launchd/com.user.trading-bot-monitor.plist` |
| `make monitor-uninstall` | `launchctl bootout gui/$(id -u) deploy/launchd/com.user.trading-bot-monitor.plist` |
| `make monitor-once` | `python -m mcp_server.monitor` |
| `make monitor-dry-run` | `python -m mcp_server.monitor --dry-run` |

---

## 6. Email delivery — direct SMTP via stdlib `smtplib`

The original "system `mail` command" decision was reverted after confirming the laptop has no MTA configured to relay externally (postfix not running, no `relayhost`, no `sasl_passwd`). Configuring postfix or installing `msmtp` was rejected as over-fragile for a single-user tool. Instead, the notifier uses Python's stdlib `smtplib` to talk directly to Gmail (or any SMTP relay).

**Required env vars:**
- `SMTP_HOST` (e.g., `smtp.gmail.com`)
- `SMTP_PORT` (default `587`)
- `SMTP_USER` (full Gmail address)
- `SMTP_PASSWORD` (Gmail **app password** — not the regular account password; create one at myaccount.google.com → Security → App passwords)
- `ALERT_EMAIL_FROM` (typically same as `SMTP_USER`)
- `ALERT_EMAIL_TO` (single recipient)

**Behavior:**
- Connect with STARTTLS on `SMTP_PORT`; raise on missing required env vars.
- One digest email per `evaluate_alerts` pass that produces ≥1 fire. Subject: `[trading-bot] N alert(s) fired: TSLA, BTC`. Body lists each fire with symbol, condition, observed values, threshold, and timestamp. Both plaintext and HTML alternatives are sent.
- Retry once on transient SMTP errors (timeout, 4xx). Log success and failure.
- `dry_run=True`: render and return the MIME message without sending — used by tests and the dry-run scheduler.

**Setup verification:** `send_test_email` constructs and sends a one-line message via the same code path; it's the explicit "does my SMTP config work" tool.

**Testability:** unit tests mock `smtplib.SMTP` and assert that the constructed `EmailMessage` carries the expected subject, recipients, plaintext body, and HTML body for a known fire batch.

---

## 7. Dependencies and env vars

**Add to `pyproject.toml`:**

```toml
dependencies = [
    # ... existing v1 deps ...
    "pandas_market_calendars>=4.4.0",
]
```

`pandas_market_calendars` pulls in `pytz` and a few small data files; the install footprint is modest.

**No third-party email library needed** — `smtplib`, `email.message`, `email.mime` are all stdlib.

**Env vars (additive):**

| Variable | Required? | Purpose |
|---|---|---|
| `SMTP_HOST` | yes | SMTP server hostname (e.g., `smtp.gmail.com`). |
| `SMTP_PORT` | no | SMTP port (default `587`). |
| `SMTP_USER` | yes | SMTP auth username (full email address for Gmail). |
| `SMTP_PASSWORD` | yes | Gmail **app password**, not the account password. |
| `ALERT_EMAIL_FROM` | yes | Sender address (typically same as `SMTP_USER`). |
| `ALERT_EMAIL_TO` | yes | Recipient address. |

The existing `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` are still required for live quotes during evaluation.

---

## Resolved decisions

1. **Schedule trigger:** launchd, every 10 min during NYSE hours, weekdays only. Stocks _and_ BTC are only checked during these windows.
2. **Alert deduplication:** `add_alert` rejects exact duplicates of (symbol, condition_type, params), returning `{"error": "duplicate alert", "existing_id": ...}`.
3. **Fire history retention:** none in v2 — `fires.jsonl` grows unbounded. Add a rotate-on-write only if it ever exceeds a few MB.
4. **Cooldown semantics:** measured from `last_fired_at`. A 24-h cooldown means at most one email per day per alert, regardless of how long the underlying condition keeps holding.
5. **Email transport:** Gmail SMTP via stdlib `smtplib`. Generate a Gmail app password (myaccount.google.com → Security → App passwords) before Prompt 4.

All decisions locked. Ready for Prompt 2.
