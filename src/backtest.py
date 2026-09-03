"""Walk-forward backtest of the days-to-cover cross-sectional signal.

Design decisions that keep this honest:

* ENTRY/EXIT LAG. Short interest for a settlement date is not public that
  day. Firms report by 6pm ET on the 2nd business day after settlement, and
  FINRA disseminates the consolidated file after that. We therefore act on a
  settlement date's data only ``LAG_TRADING_DAYS`` trading days later, and we
  apply the SAME lag to the exit, so the holding window stays ~one settlement
  interval. Acting on the settlement date's close itself would be lookahead.

* NO PARAMETER FITTING ON OOS. The signal has essentially nothing to tune:
  the direction (short high days-to-cover) is pre-registered from the
  literature, and terciles are a fixed, non-optimised split. The "walk
  forward" here is a strict in-sample / out-of-sample time split: the
  in-sample block is used ONLY to confirm the sign of the relationship; the
  OOS block is then the untouched test. Because there is nothing to overfit,
  a suspiciously good OOS number would itself be the red flag.

* REAL COSTS EVERY REBALANCE. Every settlement interval fully re-forms the
  book, so every leg pays a round-trip cost (see signal.build_period_trades).
  We report a sweep over cost levels so the reader can see where any edge dies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from metrics import summarize, portfolio_metrics, PERIODS_PER_YEAR
from strategy import rank_terciles, build_period_trades

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

LAG_TRADING_DAYS = 4     # act on short-interest data this many trading days after settlement
IS_FRACTION = 0.60       # first 60% of periods = in-sample; last 40% = OOS
DEFAULT_COST_BPS = 5.0   # per side; liquid names, Alpaca zero-commission => ~half-spread + slippage


@dataclass
class PeriodResult:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    n_long: int
    n_short: int
    net_pnl: float          # portfolio return this period, net of costs
    gross_pnl: float
    benchmark_pnl: float    # equal-weight long-only basket over same window


def load_data():
    si = pd.read_parquet(DATA_DIR / "short_interest.parquet")
    prices = pd.read_parquet(DATA_DIR / "prices.parquet")
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    # days_to_cover panel: settlement_date (rows) x symbol (cols)
    dtc = si.pivot_table(index="settlement_date", columns="symbol", values="days_to_cover")
    dtc.index = pd.to_datetime(dtc.index)
    dtc = dtc.sort_index()
    return dtc, prices


def _entry_index(prices: pd.DataFrame, settle_date: pd.Timestamp, lag: int) -> int | None:
    """Position in the price index `lag` trading days after `settle_date`.

    Returns None if there aren't enough trading days after the settlement
    date (e.g. the very last period, whose exit would fall past our data).
    """
    pos = prices.index.searchsorted(settle_date, side="left")  # first trading day >= settle_date
    target = pos + lag
    if target >= len(prices.index):
        return None
    return target


def run(cost_bps: float = DEFAULT_COST_BPS, long_high_dtc: bool = False,
        lag: int = LAG_TRADING_DAYS):
    dtc, prices = load_data()
    settle_dates = list(dtc.index)

    period_results: list[PeriodResult] = []
    all_trades = []

    for i in range(len(settle_dates) - 1):
        d0, d1 = settle_dates[i], settle_dates[i + 1]
        e_idx, x_idx = _entry_index(prices, d0, lag), _entry_index(prices, d1, lag)
        if e_idx is None or x_idx is None or x_idx <= e_idx:
            continue
        entry_prices = prices.iloc[e_idx]
        exit_prices = prices.iloc[x_idx]

        scores = {s: dtc.loc[d0, s] for s in dtc.columns}
        # only rank names that have a tradeable price at both endpoints
        scores = {s: v for s, v in scores.items()
                  if s in entry_prices.index
                  and np.isfinite(entry_prices.get(s, np.nan))
                  and np.isfinite(exit_prices.get(s, np.nan))
                  and entry_prices.get(s, 0) > 0}
        low, high = rank_terciles(scores)
        if not low or not high:
            continue

        trades = build_period_trades(
            i, low, high,
            entry_prices=entry_prices.to_dict(), exit_prices=exit_prices.to_dict(),
            cost_bps=cost_bps, long_high_dtc=long_high_dtc,
        )
        if not trades:
            continue
        all_trades.extend(trades)
        net = sum(t.net_pnl for t in trades)
        gross = sum(t.gross_pnl for t in trades)

        # benchmark: equal-weight long-only over all ranked names, same window
        rets = [exit_prices[s] / entry_prices[s] - 1 for s in scores]
        bench = float(np.mean(rets)) if rets else 0.0

        period_results.append(PeriodResult(
            entry_date=prices.index[e_idx], exit_date=prices.index[x_idx],
            n_long=len(low), n_short=len(high),
            net_pnl=net, gross_pnl=gross, benchmark_pnl=bench,
        ))

    return period_results, all_trades


def split_report(period_results: list[PeriodResult]) -> dict:
    net = np.array([p.net_pnl for p in period_results])
    bench = np.array([p.benchmark_pnl for p in period_results])
    n = len(net)
    cut = int(n * IS_FRACTION)

    def block(sl):
        return {
            "strategy": portfolio_metrics(net[sl]),
            "benchmark_longonly": portfolio_metrics(bench[sl]),
        }

    return {
        "n_periods": n,
        "in_sample": block(slice(0, cut)),
        "out_of_sample": block(slice(cut, n)),
        "full_sample": block(slice(0, n)),
    }


def _fmt(m: dict) -> str:
    if m.get("n_periods", 0) == 0:
        return "  (no periods)"
    return (f"  periods={m['n_periods']}  total_return={m['total_return']*100:+.2f}%  "
            f"mean/period={m['mean_period_return']*100:+.3f}%  "
            f"Sharpe(ann)={m['sharpe_annualized']:+.2f}  win_rate={m['win_rate']*100:.1f}%  "
            f"maxDD={m['max_drawdown']*100:.2f}%")


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    print("=" * 78)
    print("Days-to-cover cross-sectional long/short -- pre-registered direction:")
    print("  LONG lowest-days-to-cover tercile, SHORT highest-days-to-cover tercile")
    print(f"  entry/exit lag = {LAG_TRADING_DAYS} trading days after each settlement date")
    print("=" * 78)

    # Cost sweep on the pre-registered direction.
    print("\nCOST SENSITIVITY (full sample, pre-registered direction):")
    for cb in (0.0, 5.0, 10.0, 20.0):
        pr, _ = run(cost_bps=cb)
        m = portfolio_metrics(np.array([p.net_pnl for p in pr]))
        print(f"  cost={cb:5.1f}bps/side ->{_fmt(m)}")

    # Headline run at the default cost.
    pr, trades = run(cost_bps=DEFAULT_COST_BPS)
    rep = split_report(pr)
    print(f"\nHEADLINE (cost={DEFAULT_COST_BPS}bps/side):")
    for name in ("in_sample", "out_of_sample", "full_sample"):
        print(f"\n[{name}] strategy:")
        print(_fmt(rep[name]["strategy"]))
        print(f"[{name}] benchmark (equal-weight long-only basket):")
        print(_fmt(rep[name]["benchmark_longonly"]))

    # Contrarian mirror, for honesty.
    pr_c, _ = run(cost_bps=DEFAULT_COST_BPS, long_high_dtc=True)
    rep_c = split_report(pr_c)
    print("\nCONTRARIAN MIRROR (long high-DTC / short low-DTC), for reference:")
    print("[out_of_sample]" + _fmt(rep_c["out_of_sample"]["strategy"]))

    # OUTLIER ROBUSTNESS: is the OOS result driven by one lucky period?
    # This is the single most important honesty check here.
    oos = pr[int(len(pr) * IS_FRACTION):]
    oos_net = np.array([p.net_pnl for p in oos])
    top = max(oos, key=lambda p: p.net_pnl)
    ex_top = oos_net.sum() - oos_net.max()
    robustness = {
        "oos_total_return": float(oos_net.sum()),
        "oos_best_period_return": float(oos_net.max()),
        "oos_best_period": f"{top.entry_date.date()}..{top.exit_date.date()}",
        "oos_total_ex_best_period": float(ex_top),
        "oos_median_period_return": float(np.median(oos_net)),
        "oos_periods_positive": int((oos_net > 0).sum()),
        "oos_n_periods": int(len(oos_net)),
    }
    print("\nOOS OUTLIER ROBUSTNESS:")
    print(f"  OOS total={oos_net.sum()*100:+.1f}%  best single period={oos_net.max()*100:+.1f}% "
          f"({robustness['oos_best_period']})")
    print(f"  OOS total EXCLUDING that one period={ex_top*100:+.1f}%  "
          f"median period={np.median(oos_net)*100:+.2f}%  "
          f"positive periods={robustness['oos_periods_positive']}/{len(oos_net)}")

    # Per-leg trade-math summary (house-style), sanity + parity with unit tests.
    print("\nPer-leg trade summary (all legs, headline run):")
    print(" ", summarize(trades))

    out = {
        "config": {"cost_bps": DEFAULT_COST_BPS, "lag_trading_days": LAG_TRADING_DAYS,
                    "is_fraction": IS_FRACTION, "periods_per_year": PERIODS_PER_YEAR},
        "pre_registered_direction": rep,
        "contrarian_mirror": rep_c,
        "oos_outlier_robustness": robustness,
        "per_leg_summary": summarize(trades),
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {RESULTS_DIR / 'summary.json'}")
    return out


if __name__ == "__main__":
    main()
