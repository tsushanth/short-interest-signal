# short-interest-signal

Does aggregate short interest give a real trading signal? Test of a
cross-sectional **days-to-cover** signal on real, official **FINRA**
bi-monthly short interest data, walk-forward, with real transaction costs.

**Answer: no reliable edge in this basket/window.** The pre-registered
direction has the right *sign* (heavily-shorted names underperform, matching
the academic literature), but the out-of-sample profit is entirely one
outlier fortnight — strip it and OOS is slightly negative with a negative
median, and simply holding the basket beat the long/short. Full honest
write-up in [results/oos_result.md](results/oos_result.md).

## The signal and the hypothesis (pre-registered)

> Cross-sectionally, stocks with a **high days-to-cover ratio** (short
> interest ÷ average daily volume) subsequently **underperform** stocks with
> a low days-to-cover ratio.

This is the "short sellers are informed" hypothesis (Asquith, Pathak & Ritter
2005; Boehmer, Jones & Zhang 2008): heavily-shorted names earn lower future
returns. So the book is dollar-neutral **long the least-shorted tercile,
short the most-shorted tercile**, rebalanced each settlement (~24×/year),
held one settlement interval (~2 weeks — matching the data's real update
cadence, not forced faster). The competing squeeze/contrarian story (extreme
short interest → bullish) is *not* pre-registered; we report its mirror for
honesty (it loses badly, confirming the sign).

Days-to-cover is used rather than short-interest-%-of-float because the free
FINRA file provides short position and average daily volume directly, but not
shares outstanding. Days-to-cover is itself a standard short-interest ratio.

## Data — real and official

**Short interest**: FINRA's consolidated bi-monthly equity short interest
files, downloaded directly from FINRA's own CDN:

```
https://cdn.finra.org/equity/otcmarket/biweekly/shrt{YYYYMMDD}.csv
```

This is the data behind FINRA's public
[Equity Short Interest catalog](https://www.finra.org/finra-data/browse-catalog/equity-short-interest),
reported by member firms under FINRA Rule 4560. Free, no credentials, not
scraped from a third party. Pipe-delimited; the fields we use are
`currentShortPositionQuantity`, `averageDailyVolumeQuantity`,
`daysToCoverQuantity`, and the settlement date.

**Coverage constraint (from FINRA's own file page):** *"Prior to June 2021,
the data contains short interest positions in over-the-counter securities
only and does not reflect short interest data in exchange-listed securities."*
Since we trade exchange-listed names, the backtest starts **2021-06-15** and
`finra_short_interest.py` refuses earlier windows rather than silently
dropping every symbol.

Settlement dates (twice monthly, near the 15th and the last business day)
shift with weekends/holidays. Rather than hard-code FINRA's schedule (they
publish it only ~2 years forward), the loader computes the nominal date and
probes the CDN backwards a few days until it hits a real file (missing files
return HTTP 403), so it is self-correcting across the whole history.

**Prices**: daily split/dividend-adjusted closes from `yfinance` for the
basket. The loader fails loud if yfinance returns nothing for a symbol
(a known yfinance failure mode on some tickers).

**Basket**: 24 liquid, non-mega-cap, high-short-interest names (ROKU, ETSY,
DKNG, CVNA, PLUG, BYND, RIVN, AFRM, UPST, W, CHWY, BILL, LYFT, SNAP, RBLX,
PINS, COIN, HOOD, SOFI, DOCU, LCID, DASH, TDOC, OPEN). Chosen for liquidity +
short-interest presence, not for past returns — but see the survivorship
caveat below.

## Result summary (5 bps/side, 124 settlement intervals, 2021–2026)

| Block | Strategy total | Sharpe(ann) | Win rate | Max DD | Long-only basket |
|---|---|---|---|---|---|
| In-sample (74) | +79.6% | 0.79 | 58% | −34% | −51.8% |
| **Out-of-sample (50)** | **+45.3%** | **0.48** | **48%** | **−68%** | **+164%** |
| Full (124) | +124.9% | 0.63 | 54% | −68% | +112% |

**Why the positive OOS is not believed** (details in results/oos_result.md):
- OOS total **+45.3%**, but the single best fortnight alone was **+49.4%** —
  OOS **excluding that one period is −4.1%**, median period **−0.12%**, only
  **24/50** periods positive.
- The plain long-only basket returned **+164%** OOS; a dollar-neutral book
  gave that up.
- OOS max drawdown **−68%**.

The *sign* is real (the contrarian mirror loses −65% OOS), consistent with the
informed-short literature — but the effect is too weak, too concentrated, and
too beta-dominated to trade as a standalone strategy here.

### Honesty caveats
- **Survivorship bias**: the basket is names still liquid/listed *today*;
  delisted/acquired high-short names from 2021–2023 are missing. Flatters both
  strategy and benchmark.
- Single fixed basket, no universe reconstitution.
- Days-to-cover, not short-interest-%-of-float (float data not in the free file).

## Layout

```
src/
  finra_short_interest.py  # download + parse real FINRA files (self-correcting date probe)
  build_dataset.py         # basket definition; pull FINRA + yfinance -> data/*.parquet
  strategy.py              # Trade primitive, tercile ranking, per-period leg construction
  metrics.py               # per-leg summarize() + portfolio_metrics() (bi-monthly Sharpe)
  backtest.py              # walk-forward IS/OOS, cost sweep, outlier-robustness check
  live_executor.py         # DRY-RUN ONLY executor (never submits; not scheduled)
  risk_gates.py            # reused from alpaca-paper-trader (hard risk limits)
  alpaca_adapter.py        # reused from alpaca-paper-trader (GatedOrderRouter)
  env_loader.py            # reused (Alpaca paper creds, presence-checked, never printed)
tests/                     # test_strategy.py, test_metrics.py (PnL/cost/Sharpe math)
results/                   # oos_result.md, summary.json, backtest_output.txt
data/                      # short_interest.parquet, prices.parquet (raw FINRA files gitignored)
```

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python src/build_dataset.py     # downloads ~125 real FINRA files + yfinance prices
python src/backtest.py          # prints IS/OOS + robustness; writes results/
python -m pytest tests/ -q      # signal/PnL/metrics math
python src/live_executor.py     # DRY-RUN: prints intended orders, submits nothing
```

## Live executor — dry-run only, by design

`live_executor.py` computes the current signal from the latest real FINRA
file and routes every intended order through the **same** `RiskGate` used by a
live system (reused from `alpaca-paper-trader`), printing what it *would*
submit. `DRY_RUN=True` is hard-coded and load-bearing: **no order is ever sent
to Alpaca, and nothing is scheduled.** Given the no-edge result above, there
is no reason to run it live; it exists to prove the plumbing and risk gates,
not to trade.
