"""Typed dicts for data-layer return shapes."""
from __future__ import annotations

from typing import TypedDict


class Bar(TypedDict):
    date: str       # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistory(TypedDict):
    symbol: str
    source: str     # "alpaca" | "coingecko" | "yfinance"
    bars: list[Bar]


class Quote(TypedDict):
    symbol: str
    source: str
    price: float
    change_pct: float | None
    volume: float | None
    as_of: str      # ISO datetime


class NewsItem(TypedDict):
    date: str       # ISO datetime
    title: str
    source: str
    url: str
    summary: str


class NewsResult(TypedDict):
    symbol: str
    source: str
    items: list[NewsItem]


class ErrorResult(TypedDict, total=False):
    error: str
    symbol: str
