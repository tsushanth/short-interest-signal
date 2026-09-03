"""Pull real, official FINRA consolidated short interest data.

Source (verified real, not scraped from a third party): FINRA publishes a
bi-monthly consolidated equity short interest file directly on its own CDN:

    https://cdn.finra.org/equity/otcmarket/biweekly/shrt{YYYYMMDD}.csv

where YYYYMMDD is the *settlement date*. This is the same data behind
FINRA's public "Equity Short Interest" catalog
(https://www.finra.org/finra-data/browse-catalog/equity-short-interest),
reported to FINRA by member firms under Rule 4560. It is free and needs no
credentials.

IMPORTANT coverage note, straight from FINRA's own file page: "Prior to
June 2021, the data contains short interest positions in over-the-counter
securities only and does not reflect short interest data in exchange-listed
securities." So for exchange-listed (NYSE/Nasdaq) names -- which is what we
trade -- only files from 2021-06-15 onward are usable. This module refuses
to go earlier.

The file is pipe-delimited (despite the .csv extension). Columns:
    accountingYearMonthNumber | symbolCode | issueName |
    issuerServicesGroupExchangeCode | marketClassCode |
    currentShortPositionQuantity | previousShortPositionQuantity |
    stockSplitFlag | averageDailyVolumeQuantity | daysToCoverQuantity |
    revisionFlag | changePercent | changePreviousNumber | settlementDate

Settlement dates are twice a month (a business day on/around the 15th and
the last business day of the month) but the exact date shifts with weekends
and holidays. Rather than hard-code FINRA's schedule (which they only
publish a couple of years forward), we compute the nominal date and probe
the CDN backwards a few days until we hit a real file (HTTP 200). Missing
files return 403, so the probe is unambiguous and self-correcting.
"""
from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

CDN_TEMPLATE = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{ymd}.csv"
FIRST_EXCHANGE_LISTED = date(2021, 6, 15)  # earlier files are OTC-only
# A plain UA -- FINRA's CDN serves the file to curl fine, but requests'
# default UA is occasionally throttled; be explicit and polite.
_HEADERS = {"User-Agent": "short-interest-signal research (github.com/tsushanth)"}

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "finra_raw"


def _nominal_settlement_dates(start: date, end: date) -> list[date]:
    """Candidate settlement dates: the 15th and the last day of each month
    in range. The real file may sit a few days earlier (weekend/holiday
    roll-back); ``resolve_and_download`` probes for the actual one.
    """
    out: list[date] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        mid = date(y, m, 15)
        # last calendar day of month
        nxt = date(y + (m == 12), (m % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        for d in (mid, last):
            if start <= d <= end:
                out.append(d)
        y, m = (y + (m == 12), (m % 12) + 1)
    return out


def _fetch(ymd: str) -> bytes | None:
    url = CDN_TEMPLATE.format(ymd=ymd)
    r = requests.get(url, headers=_HEADERS, timeout=60)
    if r.status_code == 200 and len(r.content) > 1000:
        return r.content
    return None


def resolve_and_download(nominal: date, cache_dir: Path = RAW_DIR, max_rollback: int = 6) -> Path | None:
    """Find the real file at/just-before ``nominal`` and cache it.

    Returns the cached path, or None if no file exists in the probe window
    (e.g. a period FINRA simply didn't publish, or a future date). Walks
    backward day by day: the settlement date is always on/before the
    nominal 15th/last-of-month, never after.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    for back in range(max_rollback + 1):
        d = nominal - timedelta(days=back)
        ymd = d.strftime("%Y%m%d")
        cached = cache_dir / f"shrt{ymd}.csv"
        if cached.exists():
            return cached
        content = _fetch(ymd)
        if content is not None:
            cached.write_bytes(content)
            return cached
    return None


def parse_file(path: Path) -> pd.DataFrame:
    """Parse one FINRA short interest file into a tidy DataFrame.

    Keeps the columns we actually use and coerces numerics. ``days_to_cover``
    is taken straight from FINRA (their currentShortPosition/ADV); we don't
    recompute it, so we inherit their rounding and their handling of
    zero-volume names.
    """
    df = pd.read_csv(path, sep="|", dtype=str)
    cols = {
        "symbolCode": "symbol",
        "issueName": "name",
        "issuerServicesGroupExchangeCode": "exchange",
        "currentShortPositionQuantity": "short_interest",
        "previousShortPositionQuantity": "prev_short_interest",
        "averageDailyVolumeQuantity": "avg_daily_volume",
        "daysToCoverQuantity": "days_to_cover",
        "changePercent": "change_pct",
        "settlementDate": "settlement_date",
    }
    df = df[list(cols)].rename(columns=cols)
    for c in ("short_interest", "prev_short_interest", "avg_daily_volume",
              "days_to_cover", "change_pct"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["settlement_date"] = pd.to_datetime(df["settlement_date"]).dt.date
    return df


def load_short_interest(start: date, end: date, symbols: list[str] | None = None,
                        cache_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Download (with caching) and stack all settlement files in [start, end].

    If ``symbols`` is given, filters to those (upper-cased) to keep memory
    small. Returns a long DataFrame with one row per (settlement_date, symbol).
    Fails loud if the exchange-listed coverage window is violated.
    """
    if start < FIRST_EXCHANGE_LISTED:
        raise ValueError(
            f"start={start} predates {FIRST_EXCHANGE_LISTED}, before which FINRA's file "
            "is OTC-only and excludes exchange-listed names -- refusing to load a window "
            "that would silently drop every symbol we trade."
        )
    want = set(s.upper() for s in symbols) if symbols else None
    frames = []
    resolved_dates = []
    for nominal in _nominal_settlement_dates(start, end):
        path = resolve_and_download(nominal)
        if path is None:
            continue
        df = parse_file(path)
        if want is not None:
            df = df[df["symbol"].str.upper().isin(want)]
        frames.append(df)
        if not df.empty:
            resolved_dates.append(df["settlement_date"].iloc[0])
    if not frames:
        raise RuntimeError(f"no FINRA files resolved in [{start}, {end}] -- check connectivity")
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["settlement_date", "symbol"]).reset_index(drop=True)
    return out


if __name__ == "__main__":
    # Smoke test: pull the two most recent settlement files for a few names.
    import sys
    df = load_short_interest(date(2026, 7, 1), date(2026, 8, 31),
                             symbols=["ROKU", "ETSY", "DKNG", "CVNA"])
    print(df.to_string(index=False))
    print(f"\nsettlement dates seen: {sorted(df['settlement_date'].unique())}", file=sys.stderr)
