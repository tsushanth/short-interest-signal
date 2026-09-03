import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import Trade
from metrics import summarize, portfolio_metrics


def test_summarize_empty():
    assert summarize([]) == {"n_trades": 0}


def test_summarize_known_pnls():
    trades = [
        Trade(0, 1, 1, 10.0, 12.0, 1.0, 0.1),   # +2.0 - 0.1 = 1.9
        Trade(0, 1, 1, 10.0, 9.0, 1.0, 0.1),    # -1.0 - 0.1 = -1.1
    ]
    m = summarize(trades)
    assert m["n_trades"] == 2
    assert abs(m["net_pnl"] - 0.8) < 1e-9
    assert abs(m["total_fees"] - 0.2) < 1e-9
    assert m["win_rate"] == 0.5


def test_summarize_drawdown_nonpositive():
    trades = [
        Trade(0, 1, 1, 10.0, 15.0, 1.0, 0.0),   # +5
        Trade(0, 1, 1, 10.0, 8.0, 1.0, 0.0),    # -2
        Trade(0, 1, 1, 10.0, 7.0, 1.0, 0.0),    # -3
    ]
    assert summarize(trades)["max_drawdown"] <= 0.0


def test_portfolio_metrics_empty():
    assert portfolio_metrics([]) == {"n_periods": 0}


def test_portfolio_metrics_known_series():
    # period returns: +0.10, -0.10, +0.20
    m = portfolio_metrics([0.10, -0.10, 0.20])
    assert m["n_periods"] == 3
    assert abs(m["total_return"] - 0.20) < 1e-9        # cumulative sum
    assert abs(m["max_drawdown"] - (-0.10)) < 1e-9     # equity 0.1 -> 0.0 -> 0.2
    assert abs(m["win_rate"] - 2 / 3) < 1e-9
    assert m["sharpe_annualized"] > 0                  # mean positive


def test_portfolio_metrics_sharpe_scales_with_frequency():
    series = [0.01, 0.02, -0.01, 0.03, 0.00]
    m24 = portfolio_metrics(series, periods_per_year=24)
    m12 = portfolio_metrics(series, periods_per_year=12)
    # same series, higher frequency annualisation -> larger annualised Sharpe
    assert m24["sharpe_annualized"] > m12["sharpe_annualized"] > 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("all tests passed")
