"""Signal construction and the per-leg PnL primitive.

HYPOTHESIS (pre-registered, written before looking at any OOS result):

  Cross-sectionally, stocks with a HIGH days-to-cover ratio (short
  interest / average daily volume) subsequently UNDERPERFORM stocks with
  a LOW days-to-cover ratio.

  This is the "short sellers are informed" hypothesis from the academic
  literature (Asquith, Pathak & Ritter 2005; Boehmer, Jones & Zhang
  2008): heavily-shorted names earn lower future returns, so a
  dollar-neutral book that is long the least-shorted names and short the
  most-shorted names should earn a positive spread.

  The competing "short squeeze / contrarian" story says the opposite --
  extreme short interest is fuel for a squeeze, hence bullish. We do NOT
  pre-register that; we test the informed-short direction as the headline
  and report what the contrarian sign would have done for honesty.

Why days-to-cover and not short-interest-as-%-of-float: the free FINRA
file gives short position and average daily volume (hence days-to-cover)
directly, but NOT shares outstanding / float. Days-to-cover is itself a
standard, widely-used "short interest ratio", so we use it as the signal
and avoid bolting on a second, lower-quality data source for float.

The signal updates only as fast as the data does (bi-monthly), so the
holding period is one settlement interval (~2 weeks). We do not
manufacture a faster horizon the data cannot support.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Trade:
    """One position leg: a single name held over one settlement interval.

    Matches mm-backtester's ``Trade`` shape so ``metrics.summarize`` works
    unchanged. ``entry_tick``/``exit_tick`` are settlement-period indices
    (consecutive integers), so ``exit_tick - entry_tick == 1`` for a normal
    hold.

    Notionals are normalised so each side of the book is 1.0 gross: a long
    leg has ``qty = weight / entry_price`` with ``direction=+1``; a short
    leg the same with ``direction=-1``. Then ``gross_pnl`` equals
    ``signed_weight * simple_return`` -- i.e. the leg's contribution to the
    portfolio return in return units.
    """
    entry_tick: int
    exit_tick: int
    direction: int          # +1 = long, -1 = short
    entry_price: float
    exit_price: float
    qty: float
    fees: float

    @property
    def gross_pnl(self) -> float:
        return self.direction * (self.exit_price - self.entry_price) * self.qty

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.fees


def rank_terciles(scores: dict[str, float]) -> tuple[list[str], list[str]]:
    """Split names into low/high terciles by score (days-to-cover).

    Returns ``(low_third, high_third)``. Names with a NaN score are
    dropped. Ties are broken by the sort, which is deterministic. With
    fewer than 3 valid names, returns empty lists (nothing to trade).
    """
    valid = {s: v for s, v in scores.items() if v is not None and not np.isnan(v)}
    if len(valid) < 3:
        return [], []
    ordered = sorted(valid, key=lambda s: valid[s])
    k = len(ordered) // 3
    low_third = ordered[:k]
    high_third = ordered[-k:]
    return low_third, high_third


def build_period_trades(
    entry_tick: int,
    low_names: list[str],
    high_names: list[str],
    entry_prices: dict[str, float],
    exit_prices: dict[str, float],
    cost_bps: float,
    long_high_dtc: bool = False,
) -> list[Trade]:
    """Construct the Trade legs for one settlement interval.

    Under the pre-registered hypothesis (``long_high_dtc=False``) we LONG
    the low-days-to-cover names and SHORT the high ones. Setting
    ``long_high_dtc=True`` flips to the contrarian/squeeze direction, used
    only to report the mirror result.

    Each side is equal-weighted to 1.0 gross notional, so the book is
    dollar-neutral. ``cost_bps`` is charged per side, round-trip (entry +
    exit) => ``2 * cost_bps`` per leg, on that leg's notional.
    """
    long_side, short_side = (high_names, low_names) if long_high_dtc else (low_names, high_names)
    trades: list[Trade] = []
    cost_frac = cost_bps / 1e4

    for names, direction in ((long_side, 1), (short_side, -1)):
        if not names:
            continue
        weight = 1.0 / len(names)  # each side sums to 1.0 gross notional
        for sym in names:
            ep, xp = entry_prices.get(sym), exit_prices.get(sym)
            if ep is None or xp is None or ep <= 0 or np.isnan(ep) or np.isnan(xp):
                continue
            qty = weight / ep
            fees = weight * 2 * cost_frac  # round-trip cost on this leg's notional
            trades.append(Trade(entry_tick, entry_tick + 1, direction, ep, xp, qty, fees))
    return trades
