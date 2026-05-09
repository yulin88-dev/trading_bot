"""Email subject + plaintext + HTML body rendering for digest emails.

Pure functions; no I/O. Each `evaluate_alerts` pass that produces ≥1
fires renders one digest email. Fire dicts are the items returned in
`evaluate_alerts`'s `fires` list (see alerts/evaluator.py).
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape as h


def _condition_label(condition_type: str, params: dict | None) -> str:
    p = params or {}
    if condition_type == "price_above":
        return f"price > ${p.get('target', '?')}"
    if condition_type == "price_below":
        return f"price < ${p.get('target', '?')}"
    if condition_type == "price_crosses_above":
        return f"price crosses above ${p.get('target', '?')}"
    if condition_type == "price_crosses_below":
        return f"price crosses below ${p.get('target', '?')}"
    if condition_type == "rsi_above":
        return f"RSI({p.get('period', 14)}) > {p.get('threshold', '?')}"
    if condition_type == "rsi_below":
        return f"RSI({p.get('period', 14)}) < {p.get('threshold', '?')}"
    if condition_type == "sma_cross_above":
        return f"SMA({p.get('fast', '?')}) crosses above SMA({p.get('slow', '?')})"
    if condition_type == "sma_cross_below":
        return f"SMA({p.get('fast', '?')}) crosses below SMA({p.get('slow', '?')})"
    if condition_type == "daily_change_pct_above":
        return f"daily change > {p.get('pct', '?')}%"
    if condition_type == "daily_change_pct_below":
        return f"daily change < {p.get('pct', '?')}%"
    if condition_type == "volume_above_avg":
        return (
            f"volume > {p.get('multiplier', '?')}× "
            f"{p.get('lookback_days', 20)}-day average"
        )
    if condition_type in ("combined_and", "combined_or"):
        joiner = " AND " if condition_type == "combined_and" else " OR "
        nested = p.get("conditions") or []
        return joiner.join(
            _condition_label(n.get("condition_type", "?"), n.get("params"))
            for n in nested
        ) or condition_type
    return condition_type


def render_subject(fires: list[dict]) -> str:
    n = len(fires)
    symbols = sorted({f["symbol"] for f in fires})
    word = "alert" if n == 1 else "alerts"
    return f"[trading-bot] {n} {word} fired: {', '.join(symbols)}"


def _summary_line(fires: list[dict]) -> str:
    n = len(fires)
    word = "alert" if n == 1 else "alerts"
    symbols = sorted({f["symbol"] for f in fires})
    return f"{n} {word} fired across {len(symbols)} symbol(s): {', '.join(symbols)}"


def render_plaintext(fires: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [
        _summary_line(fires),
        "",
        f"Generated at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}.",
        "",
    ]
    for i, f in enumerate(fires, start=1):
        lines.append(f"--- Fire #{i} ---")
        lines.append(f"Symbol:    {f['symbol']}")
        lines.append(
            f"Condition: {_condition_label(f['condition_type'], f.get('params'))}"
        )
        lines.append(f"Observed:  {f.get('observed_value')}")
        lines.append(f"Threshold: {f.get('threshold')}")
        lines.append(f"At:        {f.get('fired_at', '')}")
        lines.append(f"Message:   {f.get('message', '')}")
        lines.append("")
    return "\n".join(lines)


def render_html(fires: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    rows = []
    for f in fires:
        rows.append(
            "<tr>"
            f"<td>{h(f['symbol'])}</td>"
            f"<td>{h(_condition_label(f['condition_type'], f.get('params')))}</td>"
            f"<td>{h(str(f.get('observed_value')))}</td>"
            f"<td>{h(str(f.get('threshold')))}</td>"
            f"<td>{h(f.get('fired_at', ''))}</td>"
            "</tr>"
        )
    table = (
        "<table border='1' cellpadding='6' cellspacing='0' "
        "style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>"
        "<thead><tr>"
        "<th>Symbol</th><th>Condition</th><th>Observed</th>"
        "<th>Threshold</th><th>Fired At</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return (
        "<html><body style='font-family:sans-serif'>"
        f"<h2>{h(_summary_line(fires))}</h2>"
        f"<p style='color:#666'>Generated at {h(now.strftime('%Y-%m-%dT%H:%M:%SZ'))}.</p>"
        f"{table}"
        "</body></html>"
    )


def build_digest(fires: list[dict], now: datetime | None = None) -> EmailMessage:
    """Build a multipart EmailMessage (plain + HTML) for a batch of fires."""
    msg = EmailMessage()
    msg["Subject"] = render_subject(fires)
    msg.set_content(render_plaintext(fires, now=now))
    msg.add_alternative(render_html(fires, now=now), subtype="html")
    return msg
