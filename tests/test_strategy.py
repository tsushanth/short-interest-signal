import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy import Trade, rank_terciles, build_period_trades


def test_trade_pnl_long():
    # long: exit above entry -> positive gross; fees subtract.
    t = Trade(entry_tick=0, exit_tick=1, direction=1, entry_price=100, exit_price=110, qty=2.0, fees=0.5)
    assert abs(t.gross_pnl - 20.0) < 1e-9   # (110-100)*2
    assert abs(t.net_pnl - 19.5) < 1e-9


def test_trade_pnl_short():
    # short: profits when price falls.
    t = Trade(0, 1, -1, 100, 90, 2.0, 0.5)
    assert abs(t.gross_pnl - 20.0) < 1e-9   # -1*(90-100)*2
    assert abs(t.net_pnl - 19.5) < 1e-9


def test_rank_terciles_splits_low_and_high():
    scores = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0, "F": 6.0}
    low, high = rank_terciles(scores)
    assert low == ["A", "B"]     # lowest days-to-cover
    assert high == ["E", "F"]    # highest days-to-cover


def test_rank_terciles_drops_nan_and_handles_too_few():
    assert rank_terciles({"A": 1.0, "B": float("nan")}) == ([], [])
    low, high = rank_terciles({"A": 1.0, "B": 2.0, "C": float("nan"), "D": 3.0})
    assert low == ["A"] and high == ["D"]


def test_build_period_trades_dollar_neutral_pnl_and_costs():
    # 3 low-DTC names all +10%, 3 high-DTC names all -10%.
    # Pre-registered: LONG low (gain) + SHORT high (they fall -> gain).
    low, high = ["A", "B", "C"], ["D", "E", "F"]
    entry = {s: 100.0 for s in low + high}
    exit = {**{s: 110.0 for s in low}, **{s: 90.0 for s in high}}
    trades = build_period_trades(0, low, high, entry, exit, cost_bps=5.0)

    gross = sum(t.gross_pnl for t in trades)
    fees = sum(t.fees for t in trades)
    net = sum(t.net_pnl for t in trades)
    # long book +10% (weight 1.0) + short book +10% = +0.20 gross
    assert abs(gross - 0.20) < 1e-9
    # 6 legs, each weight 1/3, round-trip cost 2*5bps -> 6 * (1/3)*2*5e-4 = 0.002
    assert abs(fees - 0.002) < 1e-12
    assert abs(net - 0.198) < 1e-9


def test_build_period_trades_contrarian_is_mirror_before_costs():
    low, high = ["A", "B", "C"], ["D", "E", "F"]
    entry = {s: 100.0 for s in low + high}
    exit = {**{s: 110.0 for s in low}, **{s: 90.0 for s in high}}
    pre = sum(t.gross_pnl for t in build_period_trades(0, low, high, entry, exit, 0.0))
    con = sum(t.gross_pnl for t in build_period_trades(0, low, high, entry, exit, 0.0, long_high_dtc=True))
    assert abs(pre + con) < 1e-9   # exact mirror when costs are zero


def test_build_period_trades_skips_bad_prices():
    low, high = ["A", "B", "C"], ["D", "E", "F"]
    entry = {s: 100.0 for s in low + high}
    entry["A"] = float("nan")   # missing price -> that leg dropped, not crashed
    exit = {**{s: 110.0 for s in low}, **{s: 90.0 for s in high}}
    trades = build_period_trades(0, low, high, entry, exit, 0.0)
    assert all(not np.isnan(t.entry_price) for t in trades)
    assert len(trades) == 5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("all tests passed")
