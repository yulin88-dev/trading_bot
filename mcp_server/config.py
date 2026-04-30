"""Configuration: env vars, symbol mapping, constants."""
from __future__ import annotations

import os
from pathlib import Path

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")

ALPACA_PAPER = True

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

SUPPORTED_SYMBOLS = ("TSLA", "BRK-B", "BTC")
DEFAULT_BENCHMARK = "SPY"

SYMBOL_MAP: dict[str, dict[str, str | None]] = {
    "TSLA":    {"alpaca": "TSLA", "yfinance": "TSLA",    "coingecko": None,      "display": "TSLA"},
    "BRK-B":   {"alpaca": "BRKB", "yfinance": "BRK-B",   "coingecko": None,      "display": "BRK-B"},
    "BRKB":    {"alpaca": "BRKB", "yfinance": "BRK-B",   "coingecko": None,      "display": "BRK-B"},
    "BRK.B":   {"alpaca": "BRKB", "yfinance": "BRK-B",   "coingecko": None,      "display": "BRK-B"},
    "BTC":     {"alpaca": None,   "yfinance": "BTC-USD", "coingecko": "bitcoin", "display": "BTC"},
    "BITCOIN": {"alpaca": None,   "yfinance": "BTC-USD", "coingecko": "bitcoin", "display": "BTC"},
    "BTC-USD": {"alpaca": None,   "yfinance": "BTC-USD", "coingecko": "bitcoin", "display": "BTC"},
    "SPY":     {"alpaca": "SPY",  "yfinance": "SPY",     "coingecko": None,      "display": "SPY"},
}


def normalize_symbol(symbol: str) -> dict[str, str | None]:
    key = symbol.upper().strip()
    if key not in SYMBOL_MAP:
        raise ValueError(f"Unsupported symbol: {symbol}")
    return SYMBOL_MAP[key]
