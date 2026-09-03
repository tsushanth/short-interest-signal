"""Performance metrics.

Two layers, deliberately separated:

- ``summarize(trades)`` aggregates a list of individual ``Trade`` legs
  (one per name per holding period). It mirrors mm-backtester's
  ``metrics.summarize`` house style so the per-trade PnL/fee/drawdown
  math is unit-testable in isolation.

- ``portfolio_metrics(period_pnl)`` works on the *portfolio* equity
  curve -- the bi-monthly net PnL series of the whole long/short book.
  This is the number that actually matters for judging the strategy, and
  its Sharpe is annualised by the real update frequency of the signal
  (short interest settles ~24 times/year), NOT by an intraday tick count.
  Annualising a bi-monthly strategy as if it traded every minute would
  massively overstate Sharpe -- a common way backtests lie.
"""
import numpy as np

# Short interest settles twice a month -> ~24 observations per year.
PERIODS_PER_YEAR = 24


def summarize(trades) -> dict:
    if not trades:
        return {"n_trades": 0}

    pnls = np.array([t.net_pnl for t in trades])
    fees = np.array([t.fees for t in trades])
    holds = np.array([t.exit_tick - t.entry_tick for t in trades])

    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max
    max_drawdown = drawdown.min() if len(drawdown) else 0.0

    return {
        "n_trades": len(trades),
        "net_pnl": float(pnls.sum()),
        "gross_pnl": float(np.array([t.gross_pnl for t in trades]).sum()),
        "total_fees": float(fees.sum()),
        "win_rate": float((pnls > 0).mean()),
        "avg_hold_periods": float(holds.mean()),
        "max_drawdown": float(max_drawdown),
    }


def portfolio_metrics(period_pnl, periods_per_year: int = PERIODS_PER_YEAR) -> dict:
    """Summarise a series of per-period portfolio PnLs (in return units,
    e.g. 0.01 == +1% of gross book that period).

    Sharpe is the mean/std of per-period returns scaled by
    sqrt(periods_per_year) -- the standard annualisation for a fixed-cadence
    strategy. No risk-free adjustment (rates are small vs the noise here and
    this is a dollar-neutral book).
    """
    pnl = np.asarray(period_pnl, dtype=float)
    if len(pnl) == 0:
        return {"n_periods": 0}

    equity = np.cumsum(pnl)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max

    mean, std = pnl.mean(), pnl.std(ddof=1) if len(pnl) > 1 else 0.0
    sharpe = (mean / std) * np.sqrt(periods_per_year) if std > 0 else 0.0

    return {
        "n_periods": len(pnl),
        "total_return": float(equity[-1]),
        "mean_period_return": float(mean),
        "std_period_return": float(std),
        "sharpe_annualized": float(sharpe),
        "win_rate": float((pnl > 0).mean()),
        "max_drawdown": float(drawdown.min()),
        "best_period": float(pnl.max()),
        "worst_period": float(pnl.min()),
    }
