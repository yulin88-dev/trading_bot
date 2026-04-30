"""Markdown templates per report section.

Each function takes plain dicts (already de-erred by the caller) and returns
a markdown fragment. None values render as 'N/A' in tables.
"""
from __future__ import annotations


def _fmt_currency(v: float | None) -> str:
    return f"${v:,.2f}" if v is not None else "N/A"


def _fmt_pct(v: float | None, signed: bool = True) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def _fmt_int(v: float | None) -> str:
    return f"{int(v):,}" if v is not None else "N/A"


def _fmt_num(v: float | None, places: int = 2) -> str:
    return f"{v:.{places}f}" if v is not None else "N/A"


def render_performance_table(
    *,
    price: float | None,
    weekly_pct: float | None,
    ytd_pct: float | None,
    week_high: float | None,
    week_low: float | None,
    avg_volume: float | None,
) -> str:
    return (
        "### Performance\n\n"
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Close | {_fmt_currency(price)} |\n"
        f"| Weekly Return | {_fmt_pct(weekly_pct)} |\n"
        f"| YTD Return | {_fmt_pct(ytd_pct)} |\n"
        f"| Week High | {_fmt_currency(week_high)} |\n"
        f"| Week Low | {_fmt_currency(week_low)} |\n"
        f"| Avg Daily Volume | {_fmt_int(avg_volume)} |\n"
    )


def render_technical_signals(t: dict | None) -> str:
    if not t or "error" in t:
        return "### Technical Signals\n\n_Data unavailable._\n"
    rsi = t.get("rsi_14")
    rsi_label = t.get("rsi_label", "")
    sma_20 = t.get("sma_20")
    sma_50 = t.get("sma_50")
    macd_line = t.get("macd_line")
    macd_hist = t.get("macd_hist")
    p20 = t.get("price_vs_sma20", "")
    p50 = t.get("price_vs_sma50", "")
    cross = t.get("crossover_signal", "")

    macd_state = (
        "above signal (bullish)"
        if macd_hist is not None and macd_hist > 0
        else "below signal (bearish)"
    )

    return (
        "### Technical Signals\n\n"
        f"- **RSI(14):** {_fmt_num(rsi, 1)} — {rsi_label}\n"
        f"- **20-day SMA:** {_fmt_currency(sma_20)} (price is {p20})\n"
        f"- **50-day SMA:** {_fmt_currency(sma_50)} (price is {p50})\n"
        f"- **MACD:** {_fmt_num(macd_line, 2)}, {macd_state}\n"
        f"- **SMA cross:** {cross}\n"
    )


def render_volatility(v: dict | None) -> str:
    if not v or "error" in v:
        return "### Volatility\n\n_Data unavailable._\n"
    vol = v.get("ann_vol_30d")
    delta = v.get("vol_delta_pct")
    if vol is None or delta is None:
        return "### Volatility\n\n_Data unavailable._\n"

    direction = (
        "expanded"
        if delta > 1.0
        else "contracted"
        if delta < -1.0
        else "held roughly flat"
    )
    commentary = (
        f"30-day annualized realized volatility is {vol:.1f}%, "
        f"{direction} by {abs(delta):.1f}pp vs the prior 30 days."
    )
    if delta > 5.0:
        commentary += " The expansion is notable and suggests rising uncertainty."
    elif delta < -5.0:
        commentary += " The contraction suggests calmer conditions."

    return f"### Volatility\n\n{commentary}\n"


def render_news(items: list[dict], limit: int = 3) -> str:
    if not items:
        return "### Top News\n\n_No headlines available._\n"
    out = ["### Top News\n"]
    for i, n in enumerate(items[:limit], start=1):
        date = (n.get("date") or "")[:10]
        title = n.get("title") or "(untitled)"
        url = n.get("url") or ""
        source = n.get("source") or ""
        if url:
            out.append(f"{i}. [{title}]({url}) — {source}, {date}")
        else:
            out.append(f"{i}. {title} — {source}, {date}")
    return "\n".join(out) + "\n"


def render_assessment(
    *,
    display: str,
    weekly_pct: float | None,
    technicals: dict | None,
    vol: dict | None,
    bench_alpha: float | None,
) -> str:
    parts: list[str] = []

    if weekly_pct is not None:
        if abs(weekly_pct) < 0.5:
            parts.append(f"{display} traded roughly flat on the week.")
        elif weekly_pct > 0:
            parts.append(f"{display} gained {weekly_pct:.1f}% on the week.")
        else:
            parts.append(f"{display} lost {abs(weekly_pct):.1f}% on the week.")

    if bench_alpha is not None:
        if bench_alpha > 1.0:
            parts.append(f"It outperformed SPY by {bench_alpha:.1f}pp.")
        elif bench_alpha < -1.0:
            parts.append(f"It lagged SPY by {abs(bench_alpha):.1f}pp.")
        else:
            parts.append("Performance was roughly in line with SPY.")

    if technicals and "error" not in technicals:
        rsi = technicals.get("rsi_14")
        cross = technicals.get("crossover_signal", "")
        p50 = technicals.get("price_vs_sma50", "")
        if rsi is not None:
            if rsi >= 70:
                parts.append(f"RSI at {rsi:.0f} flags overbought conditions.")
            elif rsi <= 30:
                parts.append(f"RSI at {rsi:.0f} flags oversold conditions.")
        if cross.startswith("bullish") and p50 == "above":
            parts.append("Price sits above the 50-day SMA with a bullish moving-average cross — constructive setup.")
        elif cross.startswith("bearish") and p50 == "below":
            parts.append("Price sits below the 50-day SMA with a bearish moving-average cross — caution warranted.")

    if vol and "error" not in vol:
        delta = vol.get("vol_delta_pct")
        if delta is not None and abs(delta) > 5.0:
            direction = "rising" if delta > 0 else "falling"
            parts.append(f"Realized vol is {direction} sharply.")

    if not parts:
        return "### Assessment\n\n_Insufficient data to assess._\n"
    return "### Assessment\n\n" + " ".join(parts) + "\n"


def render_cross_asset_table(rows: list[dict]) -> str:
    out = [
        "## Cross-Asset Comparison\n",
        "| Asset | Weekly Return | 30d Ann. Vol | Corr to SPY |",
        "|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['display']} | {_fmt_pct(r.get('weekly_pct'))} | "
            f"{_fmt_pct(r.get('vol_30d'), signed=False)} | "
            f"{_fmt_num(r.get('corr_spy'), 2)} |"
        )
    return "\n".join(out) + "\n"


def render_outlook(rows: list[dict]) -> str:
    out = ["## Outlook & Watch Items\n"]
    out.append(
        "_Earnings dates and macro events are not auto-pulled in v1; check "
        "issuer IR pages and an economic calendar manually._\n"
    )
    out.append("**Technical levels to watch:**\n")
    for r in rows:
        sma_20 = r.get("sma_20")
        sma_50 = r.get("sma_50")
        wh = r.get("week_high")
        wl = r.get("week_low")
        pieces = []
        if sma_20 is not None:
            pieces.append(f"20d SMA {_fmt_currency(sma_20)}")
        if sma_50 is not None:
            pieces.append(f"50d SMA {_fmt_currency(sma_50)}")
        if wh is not None:
            pieces.append(f"week high {_fmt_currency(wh)}")
        if wl is not None:
            pieces.append(f"week low {_fmt_currency(wl)}")
        out.append(f"- **{r['display']}:** " + " · ".join(pieces))
    return "\n".join(out) + "\n"


def render_executive_summary(rows: list[dict]) -> str:
    bullets: list[str] = []
    for r in rows:
        wpct = r.get("weekly_pct")
        alpha = r.get("alpha")
        bits = []
        if r.get("price") is not None:
            bits.append(f"closed at {_fmt_currency(r['price'])}")
        if wpct is not None:
            direction = "up" if wpct > 0 else "down" if wpct < 0 else "flat"
            bits.append(f"{direction} {abs(wpct):.1f}% on the week")
        if alpha is not None and abs(alpha) > 1.0:
            cmp_word = "outperforming" if alpha > 0 else "lagging"
            bits.append(f"{cmp_word} SPY by {abs(alpha):.1f}pp")
        if bits:
            bullets.append(f"- **{r['display']}:** " + ", ".join(bits) + ".")

    # Identify standouts: biggest mover and biggest vol shift
    movers = [(r["display"], r.get("weekly_pct")) for r in rows if r.get("weekly_pct") is not None]
    if movers:
        biggest = max(movers, key=lambda x: abs(x[1]))
        if abs(biggest[1]) >= 2.0:
            bullets.append(
                f"- Biggest mover: **{biggest[0]}** ({biggest[1]:+.1f}%)."
            )

    vol_shifts = [(r["display"], r.get("vol_delta")) for r in rows if r.get("vol_delta") is not None]
    if vol_shifts:
        biggest_vol = max(vol_shifts, key=lambda x: abs(x[1]))
        if abs(biggest_vol[1]) >= 5.0:
            direction = "expansion" if biggest_vol[1] > 0 else "contraction"
            bullets.append(
                f"- Notable vol {direction}: **{biggest_vol[0]}** ({biggest_vol[1]:+.1f}pp WoW)."
            )

    if not bullets:
        return "## Executive Summary\n\n_Insufficient data._\n"
    return "## Executive Summary\n\n" + "\n".join(bullets) + "\n"
