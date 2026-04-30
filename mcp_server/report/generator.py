"""Weekly report orchestrator.

Pulls data via the existing MCP tools (no direct vendor calls), assembles a
markdown document, and writes it to ./reports/weekly_report_YYYY-MM-DD.md.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from mcp_server.config import REPORTS_DIR, normalize_symbol
from mcp_server.report import templates
from mcp_server.tools.analysis_tools import (
    compare_to_benchmark,
    compute_technicals,
    compute_volatility,
    compute_weekly_performance,
)
from mcp_server.tools.data_tools import (
    get_current_quote,
    get_news,
    get_price_history,
)

REPORT_SYMBOLS = ("TSLA", "BRK-B", "BTC")

# Bars to fetch when computing YTD — covers Jan 1 even early in the year.
_YTD_BARS = 300


def _last_friday(today: date | None = None) -> date:
    today = today or date.today()
    days_back = (today.weekday() - 4) % 7
    return today - timedelta(days=days_back)


def _safe(d: dict | None, key: str):
    if not d or "error" in d:
        return None
    return d.get(key)


def _ytd_pct(symbol: str, year: int) -> float | None:
    """Compute return from first trading day of `year` to most recent close."""
    res = get_price_history(symbol, days=_YTD_BARS)
    bars = res.get("bars") or []
    if not bars or "error" in res:
        return None
    in_year = [b for b in bars if b["date"][:4] == str(year)]
    if len(in_year) < 2:
        return None
    first_close = float(in_year[0]["close"])
    last_close = float(bars[-1]["close"])
    if first_close == 0:
        return None
    return (last_close / first_close - 1.0) * 100.0


def _gather(symbol: str, year: int) -> dict:
    """Pull all signals for a single symbol via existing tools."""
    quote = get_current_quote(symbol)
    perf = compute_weekly_performance(symbol)
    tech = compute_technicals(symbol)
    vol = compute_volatility(symbol)
    bench = compare_to_benchmark(symbol, "SPY")
    news = get_news(symbol, days=7)
    ytd = _ytd_pct(symbol, year)

    return {
        "symbol": symbol,
        "display": normalize_symbol(symbol)["display"],
        "quote": quote,
        "performance": perf,
        "technicals": tech,
        "volatility": vol,
        "benchmark": bench,
        "news": news,
        "ytd_pct": ytd,
    }


def _summary_row(asset: dict) -> dict:
    """Flatten the gathered data to the keys templates need for tables/summary."""
    perf = asset["performance"]
    tech = asset["technicals"]
    vol = asset["volatility"]
    bench = asset["benchmark"]
    quote = asset["quote"]

    return {
        "display": asset["display"],
        "price": _safe(quote, "price"),
        "weekly_pct": _safe(perf, "weekly_return_pct"),
        "alpha": _safe(bench, "alpha"),
        "vol_30d": _safe(vol, "ann_vol_30d"),
        "vol_delta": _safe(vol, "vol_delta_pct"),
        "corr_spy": _safe(bench, "correlation_30d"),
        "sma_20": _safe(tech, "sma_20"),
        "sma_50": _safe(tech, "sma_50"),
        "week_high": _safe(perf, "week_high"),
        "week_low": _safe(perf, "week_low"),
    }


def _render_asset_section(asset: dict) -> str:
    perf = asset["performance"]
    bench = asset["benchmark"]
    quote = asset["quote"]
    news_items = asset["news"].get("items", []) if asset["news"] else []

    parts = [f"## {asset['display']}\n"]
    parts.append(
        templates.render_performance_table(
            price=_safe(quote, "price"),
            weekly_pct=_safe(perf, "weekly_return_pct"),
            ytd_pct=asset["ytd_pct"],
            week_high=_safe(perf, "week_high"),
            week_low=_safe(perf, "week_low"),
            avg_volume=_safe(perf, "avg_volume"),
        )
    )
    parts.append(templates.render_technical_signals(asset["technicals"]))
    parts.append(templates.render_volatility(asset["volatility"]))
    parts.append(templates.render_news(news_items))
    parts.append(
        templates.render_assessment(
            display=asset["display"],
            weekly_pct=_safe(perf, "weekly_return_pct"),
            technicals=asset["technicals"],
            vol=asset["volatility"],
            bench_alpha=_safe(bench, "alpha"),
        )
    )
    return "\n".join(parts)


def generate_weekly_report(week_ending: str | None = None) -> dict:
    """Build the weekly markdown report, save it, return path + summary.

    Args:
        week_ending: Optional ISO date (YYYY-MM-DD); defaults to most recent Friday.

    Returns:
        Dict with file_path, summary, week_ending_date.
    """
    week_ending_date = (
        datetime.fromisoformat(week_ending).date() if week_ending else _last_friday()
    )
    year = week_ending_date.year
    iso = week_ending_date.isoformat()

    assets = [_gather(s, year) for s in REPORT_SYMBOLS]
    rows = [_summary_row(a) for a in assets]

    sections: list[str] = [f"# Weekly Market Report — {iso}\n"]
    sections.append(templates.render_executive_summary(rows))
    sections.append("---\n")
    for a in assets:
        sections.append(_render_asset_section(a))
        sections.append("---\n")
    sections.append(templates.render_cross_asset_table(rows))
    sections.append(templates.render_outlook(rows))

    full_md = "\n".join(sections)

    REPORTS_DIR.mkdir(exist_ok=True)
    file_path = REPORTS_DIR / f"weekly_report_{iso}.md"
    file_path.write_text(full_md, encoding="utf-8")

    biggest_mover = max(
        (r for r in rows if r.get("weekly_pct") is not None),
        key=lambda r: abs(r["weekly_pct"]),
        default=None,
    )
    parts = []
    for r in rows:
        if r.get("weekly_pct") is not None:
            parts.append(f"{r['display']} {r['weekly_pct']:+.2f}%")
        else:
            parts.append(f"{r['display']} N/A")
    summary_text = f"Report for week ending {iso}: {', '.join(parts)}."
    if biggest_mover and abs(biggest_mover["weekly_pct"]) >= 2.0:
        summary_text += (
            f" Biggest mover: {biggest_mover['display']} "
            f"({biggest_mover['weekly_pct']:+.2f}%)."
        )

    return {
        "file_path": str(file_path.resolve()),
        "summary": summary_text,
        "week_ending_date": iso,
    }
