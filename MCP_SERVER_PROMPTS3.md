# Trading Bot v2 — Monitor & Alert Prompts

A structured set of prompts to extend the existing **trading-bot** MCP server
with a monitor + alert capability. After reviewing the weekly report, you
define entry-point alerts (e.g., "TSLA below $350 with RSI under 30"); the
server watches during market hours and emails you when an alert fires.

## Decisions to make first

Fill these in before using the prompts below:

- **Email delivery**:
  system `mail` command
- **Recipient**: a single email address
- **Storage**: reuse the existing `reports/` directory pattern with JSON files
- **Schedule trigger**: launchd timer (every 10 min during market hours)
- **Condition syntax**: canonical condition types with parameters
  (`price_below`, `rsi_below`, etc.) or a small DSL — recommend canonical
  for v2
- **Cooldown default**: 24 h (one fire per day)
- **Market calendar**:  `pandas_market_calendars`
  for full NYSE holiday awareness

---

## Prompt 1 — Architecture & design

```
I want to extend the existing trading-bot MCP server with a monitor +
alert capability for v2.

Background: v1 generates a weekly market report that identifies
technical levels and trends for TSLA, BRK-B, BTC, and other tickers. I
review the report, pick entry points (e.g., "alert me if TSLA falls
below $350 with RSI under 30"), and want the server to watch live
prices during market hours and email me when an alert triggers.

Goals:
- Define and manage alerts via MCP tool calls from Claude Desktop.
- Evaluate live prices on a schedule during NYSE hours; suppress
  repeat fires via per-alert cooldowns.
- Email me when an alert triggers (Gmail SMTP).
- Skip stock alerts outside NYSE hours; BTC monitored 24/7.
- Reuse the existing data tools (get_current_quote, compute_technicals,
  etc.) — no duplicated vendor calls.

Please propose:
1. Architecture: extend the existing trading-bot package vs sibling
   package. Justify based on code reuse, deployment, blast radius.
2. Alert schema: condition types, parameters, status field, cooldown,
   fire-history table.
3. The list of new MCP tools (name, inputs, outputs, purpose).
4. Scheduler design: launchd plist? On-demand? Both?
5. Email delivery: SMTP config, env vars, template structure, dry-run
   path for tests.
6. Dependencies and new env vars.

Do not write code yet. I want a design doc first.
```

---

## Prompt 2 — Alert CRUD + storage

```
Implement the alerts SQLite store and the CRUD tools.

Suggested schema:
- alerts(id, symbol, condition_type, params_json, status, cooldown_seconds,
  created_at, updated_at)
- alert_fires(id, alert_id, fired_at, observed_value, message)

Tools (mirror the prompt-library patterns):
1. add_alert(symbol, condition_type, params, cooldown_seconds=86400,
   status='active')
2. update_alert(id, **fields)
3. list_alerts(status=None, symbol=None)
4. get_alert(id)
5. pause_alert(id) / resume_alert(id)
6. delete_alert(id, confirm=False)
7. get_alert_history(alert_id=None, limit=50)

Constraints:
- Atomic per-call writes; auto-managed timestamps.
- condition_type validated against the registered set; params are
  validated against the type-specific schema (e.g., price_below requires
  `target` as a number).
- status ∈ {active, paused, archived}; reject other values.
- All tools return structured dicts; never raise (translate typed
  exceptions to {"error": "...", "id": ...}).
- delete_alert requires confirm=True.

Include unit tests covering: happy path, partial update, status
validation, params validation per condition type, cooldown range
checks, not-found, and uniqueness rules (e.g., disallow exact-duplicate
alerts on the same symbol+condition).
```

---

## Prompt 3 — Condition evaluation engine

```
Implement the condition evaluation engine plus the evaluate_alerts tool.

Each condition_type maps to a pure-Python evaluator that:
1. Fetches required data via the existing v1 data tools (get_current_quote,
   get_price_history, compute_technicals, etc.).
2. Returns {fired: bool, observed_value, threshold, message}.
3. Handles missing data and vendor errors gracefully (returns
   {fired: False, error: "..."}).

Condition types to support in v2:
- price_above(target) / price_below(target)
- price_crosses_above(target) / price_crosses_below(target)
  (requires comparing the previous close vs current to detect crossings)
- rsi_below(threshold, period=14) / rsi_above(threshold, period=14)
- sma_cross_above(fast, slow) / sma_cross_below(fast, slow)
- daily_change_pct_above(pct) / daily_change_pct_below(pct)
- volume_above_avg(multiplier, lookback_days=20)
- combined_and(conditions=[...]) — every nested condition must fire
- combined_or(conditions=[...]) — at least one must fire

Add the MCP tool:
  evaluate_alerts(symbol=None, dry_run=False)

Behavior:
- Load active alerts (optionally filtered by symbol).
- Run evaluators in a single pass; reuse a per-symbol quote cache so
  each symbol's data is fetched once.
- For each fire: respect cooldown_seconds (skip if last fire is more
  recent); insert an alert_fires row; queue an email.
- If dry_run=True, return a preview of what would fire and what the
  email would say without sending or recording.
- Return {evaluated: N, fired: M, suppressed_by_cooldown: K, errors: [...]}

Cover with unit tests using mocked data tools and a frozen clock.
```

---

## Prompt 4 — Email delivery (SMTP)

```
Implement the email notifier.

Module: trading_bot/notifier/email.py (or trading_bot/alerts/email.py)

Required env vars:
- SMTP_HOST (e.g., smtp.gmail.com)
- SMTP_PORT (default 587)
- SMTP_USER
- SMTP_PASSWORD (Gmail app password recommended; app password is NOT a
  regular Google account password)
- ALERT_EMAIL_FROM
- ALERT_EMAIL_TO (single address or comma-separated list)

Behavior:
- STARTTLS on connect; raise if any of the required env vars missing.
- Render subject + plaintext + HTML body from a template per fire,
  including: symbol, condition description, observed value vs threshold,
  timestamp, and a one-line summary at the top.
- Each evaluate_alerts pass produces ONE digest email when multiple
  alerts fire (subject lists symbols; body lists each fire).
- Retry once on transient SMTP errors; log success and failure.
- Supports dry_run=True (returns the rendered MIME message without
  sending) so tests can verify formatting.

Add the MCP tool:
  send_test_email(to=None, body=None) — sends a "hello world" using the
  configured SMTP settings to verify setup. Returns {sent: bool,
  rendered: str, error: ...}.

Unit tests with smtplib.SMTP mocked. Round-trip a sample fire batch
through the renderer and assert subject, recipients, plaintext, and
HTML are all populated correctly.
```

---

## Prompt 5 — Scheduler & market-hours awareness

```
Add the scheduler that runs evaluations on a cadence during market hours.

Components:

1. Module trading_bot/monitor.py with a `main()` entry point that:
   - Determines whether US equity markets are open right now
     (weekday + 9:30am–4:00pm ET, excluding US market holidays).
   - For stock alerts: only run if markets are open.
   - For crypto alerts (BTC): always run.
   - Calls evaluate_alerts() internally.
   - Logs the run to stderr (launchd captures to ~/Library/Logs/).

2. com.user.trading-bot-monitor.plist (in ./deploy/launchd/) with:
   - The full Python interpreter path and `-m trading_bot.monitor`.
   - StartCalendarInterval entries for every 5 minutes between 9:30 and
     16:00 ET on weekdays.
   - StandardOutPath / StandardErrorPath under ~/Library/Logs/.

3. Make targets:
   - `make monitor-install` — launchctl bootstrap the plist.
   - `make monitor-uninstall` — launchctl bootout.
   - `make monitor-once` — run main() once and exit.
   - `make monitor-dry-run` — run main() with evaluate_alerts(dry_run=True)
     and print what would fire (no emails sent).

For the market calendar: start with a hand-rolled weekday + 9:30–16:00 ET
check (use zoneinfo.ZoneInfo("America/New_York")). If you want full
holiday support, swap in pandas_market_calendars later — keep the
calendar logic isolated behind a function so the swap is one-file.
```

---

## Prompt 6 — Polish, sample prompts, and end-to-end test

```
Final pass:

1. Logging: every alert tool, the evaluator, and the notifier are wrapped
   with the existing log_tool decorator. Each fire logs the alert id,
   symbol, observed value, and whether an email was queued.

2. README updates:
   - "Alerts" section describing CRUD examples and supported condition
     types (with one-line description of each).
   - "Email setup" section: how to create a Gmail app password, which
     env vars to set, how to test with send_test_email.
   - "Scheduler setup" section: make monitor-install / monitor-uninstall /
     monitor-once / monitor-dry-run.

3. Five sample Claude Desktop prompts:
   - Add an alert ("Alert me if TSLA closes below $350 with RSI under 30,
     cooldown 24h.")
   - List active alerts ("What am I watching right now?")
   - Pause an alert ("Pause the BTC-above-80k alert until Monday.")
   - Test email setup ("Send a test alert email to confirm SMTP works.")
   - Evaluate now ("Check all my alerts now and tell me which would
     fire — but don't send any emails yet.")

4. End-to-end smoke test: seed two alerts (one stock, one BTC), mock
   live quotes so one fires and one doesn't, run evaluate_alerts in
   dry-run, assert the rendered email body, confirm cooldown logic
   suppresses a repeat fire on the next evaluation.

5. .env.example and the README list every new env var introduced
   (SMTP_*, ALERT_EMAIL_*).
```

---

## How to use these prompts

Run the prompts one at a time in a fresh session. Paste the previous
prompt's output as context into the next so each step builds on the last.
Resolve the **Decisions to make first** items before Prompt 1 — especially
the email backend and the schedule trigger, which shape Prompts 4 and 5
most directly.

When wiring this into the existing trading-bot project, keep v1 tools
unchanged. The new alert / monitor / notifier modules should land
alongside `mcp_server/data/`, `mcp_server/analysis/`, and `mcp_server/report/`,
and the new MCP tools should register in `server.py` next to the existing
ones. v1 tests should continue to pass after every prompt.
