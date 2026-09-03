"""DRY-RUN live executor for the days-to-cover long/short signal.

Follows the shape of alpaca-paper-trader's pairs_signal.py: compute the
signal against the latest real data, then route intended orders through the
SAME RiskGate / GatedOrderRouter that a live version would use -- so the
risk plumbing is exercised for real. The ONE difference, and it is
deliberate and load-bearing: DRY_RUN is True and no order is ever submitted.
This module is NOT scheduled and NOT wired to any cron.

What it does on each run:
  1. Load the most recent FINRA settlement file for the basket (real data).
  2. Rank by days-to-cover, form the pre-registered long/short book.
  3. For every intended leg, call RiskGate.check_order -- proving the order
     would pass the hard risk limits -- and print it.
  4. Stop. It never calls submit_order.

Turning this into a live executor would mean: set DRY_RUN=False, construct
the GatedOrderRouter with real (paper) keys, call router.warmup(), and
replace the print with router.submit_limit_order(...). That should be an
explicit, reviewed change -- not a default, and not something a scheduler
does on its own.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from finra_short_interest import load_short_interest
from strategy import rank_terciles
from risk_gates import RiskGate, RiskLimits

# --- basket must match build_dataset.BASKET; imported to stay in sync ---
from build_dataset import BASKET

DRY_RUN = True   # NEVER flip to False without an explicit, reviewed change.

# Conservative hard limits for a hypothetical paper deployment. These are
# safety rails, not strategy tuning (see risk_gates.py docstring).
LIMITS = RiskLimits(
    max_position_per_symbol=10,
    max_total_notional=20_000,
    max_daily_loss=500,
    max_orders_per_minute=len(BASKET) * 2 + 5,  # one entry per name + headroom
)
QTY_PER_LEG = 1   # shares per name; tiny, illustrative sizing only


def latest_signal(symbols=BASKET):
    """Pull the two most recent settlement files and return the newest one's
    cross-sectional ranking. Two files so we always have a fully-populated
    latest period even right after a new file drops.
    """
    today = date.today()
    si = load_short_interest(today - timedelta(days=45), today, symbols=symbols)
    latest_date = si["settlement_date"].max()
    latest = si[si["settlement_date"] == latest_date]
    scores = dict(zip(latest["symbol"], latest["days_to_cover"]))
    low, high = rank_terciles(scores)
    return latest_date, scores, low, high


def main():
    latest_date, scores, low, high = latest_signal()
    print(f"latest FINRA settlement date: {latest_date}")
    print(f"ranked {len(scores)} names; long {len(low)} low-DTC, short {len(high)} high-DTC")
    print(f"  LONG  (low days-to-cover):  {low}")
    print(f"  SHORT (high days-to-cover): {high}\n")

    gate = RiskGate(limits=LIMITS)
    # Intended orders: BUY the low-DTC names, SELL (short) the high-DTC names.
    intended = [(s, "BUY") for s in low] + [(s, "SELL") for s in high]

    now = time.time()
    passed, blocked = 0, 0
    for symbol, side in intended:
        # Use a nominal price of 1.0 for the gate's notional check -- this is a
        # dry run and we are not fetching a live quote; the point is to prove
        # the order clears position/rate/kill-switch gates, not to price it.
        try:
            gate.check_order(symbol, side, QTY_PER_LEG, price=1.0, now=now)
            gate.record_order_sent(now)
            gate.record_fill(symbol, side, QTY_PER_LEG, price=1.0)  # simulate fill for position tracking
            passed += 1
            print(f"  [would submit] {side:4} {QTY_PER_LEG} {symbol}  (passed risk gate)")
        except Exception as e:  # noqa: BLE001 -- surface exactly why a gate blocked
            blocked += 1
            print(f"  [BLOCKED]      {side:4} {QTY_PER_LEG} {symbol}: {e}")

    print(f"\n{passed} orders would submit, {blocked} blocked by risk gate.")
    if DRY_RUN:
        print("DRY_RUN=True -> no orders were sent to Alpaca. Nothing was traded, "
              "nothing scheduled.")
    else:  # pragma: no cover - intentionally unreachable in this repo
        raise RuntimeError("DRY_RUN is False but live submission is not enabled in this repo")


if __name__ == "__main__":
    main()
