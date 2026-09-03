"""Assemble the backtest dataset: real FINRA short interest + real yfinance
prices for a fixed basket, cached to data/ as parquet.

Basket selection (documented, since basket choice can bias results): a
fixed list of ~2 dozen liquid, non-mega-cap US equities that are known to
carry meaningful and time-varying short interest (high-short-interest growth
/ "story" names -- the population where a short-interest signal has any
chance of mattering). Names were chosen for liquidity + short-interest
presence, NOT for past returns.

Honest caveat (also stated in the README): the basket is drawn from names
that are still listed and liquid *today*, so there is mild survivorship
bias -- delisted or acquired high-short names from 2021-2023 are absent.
This tends to flatter any strategy. Read the results as illustrative of the
signal, not as a deployable, bias-free backtest.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from finra_short_interest import load_short_interest, FIRST_EXCHANGE_LISTED

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

BASKET = [
    "ROKU", "ETSY", "DKNG", "CVNA", "PLUG", "BYND", "RIVN", "AFRM",
    "UPST", "W", "CHWY", "BILL", "LYFT", "SNAP", "RBLX", "PINS",
    "COIN", "HOOD", "SOFI", "DOCU", "LCID", "DASH", "TDOC", "OPEN",
]

START = FIRST_EXCHANGE_LISTED       # 2021-06-15, first file with exchange-listed names
END = date(2026, 8, 31)


def build_short_interest(symbols=BASKET, start=START, end=END) -> pd.DataFrame:
    si = load_short_interest(start, end, symbols=symbols)
    out = DATA_DIR / "short_interest.parquet"
    si.to_parquet(out)
    print(f"short interest: {len(si)} rows, "
          f"{si['settlement_date'].nunique()} settlement dates, "
          f"{si['symbol'].nunique()} symbols -> {out}")
    return si


def build_prices(symbols=BASKET, start=START, end=END) -> pd.DataFrame:
    import yfinance as yf
    # auto_adjust=True -> split/dividend-adjusted closes, consistent for a
    # long/short book. Pull a little past END so the last holding period has
    # an exit price available.
    raw = yf.download(symbols, start=start.isoformat(), end="2026-09-15",
                      auto_adjust=True, progress=False)
    closes = raw["Close"].copy()
    # Fail loud on any symbol yfinance returned nothing for (cf. the known
    # yfinance gap on some tickers) rather than silently trading a NaN column.
    empty = [c for c in closes.columns if closes[c].notna().sum() == 0]
    if empty:
        raise RuntimeError(f"yfinance returned no data for {empty} -- fix the basket or the date range")
    missing = sorted(set(symbols) - set(closes.columns))
    if missing:
        print(f"WARNING: yfinance had no column for {missing} -- they will be skipped")
    out = DATA_DIR / "prices.parquet"
    closes.to_parquet(out)
    print(f"prices: {closes.shape[0]} trading days x {closes.shape[1]} symbols -> {out}")
    return closes


if __name__ == "__main__":
    build_short_interest()
    build_prices()
