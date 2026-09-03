# OOS result — honest read

**Bottom line: no reliable, tradeable edge.** The pre-registered direction
has the *correct sign* (consistent with the academic "shorts are informed"
literature), but the out-of-sample profit is entirely one outlier fortnight.
Strip that single period out and the OOS is slightly negative with a negative
median. This is a no-edge / at-best-marginal outcome, reported as such.

## What was tested

- **Signal**: cross-sectional days-to-cover (short interest ÷ average daily
  volume), from FINRA's real bi-monthly consolidated short interest files.
- **Pre-registered direction**: LONG the lowest-days-to-cover tercile, SHORT
  the highest. Dollar-neutral, equal-weight, rebalanced every settlement
  (~24×/year), held one settlement interval (~2 weeks).
- **Basket**: 24 liquid, non-mega-cap high-short-interest names.
- **Data window**: 2021-06-15 (first FINRA file that includes exchange-listed
  names) → 2026-08-14. 124 tradeable settlement intervals.
- **Lag**: acted on each file 4 trading days after its settlement date (data
  isn't public on the settlement date); same lag applied to the exit.
- **Costs**: charged every rebalance, per side; headline = 5 bps/side.
- **Split**: first 60% of periods in-sample, last 40% out-of-sample. Nothing
  is fit on OOS — the direction is pre-registered and terciles are fixed, so
  there is essentially nothing to overfit.

## Headline numbers (5 bps/side)

| Block | Strategy total | Strategy Sharpe(ann) | Win rate | Max DD | Long-only basket (same window) |
|---|---|---|---|---|---|
| In-sample (74) | +79.6% | 0.79 | 58% | −34% | −51.8% (Sharpe −0.37) |
| **Out-of-sample (50)** | **+45.3%** | **0.48** | **48%** | **−68%** | **+164% (Sharpe 0.96)** |
| Full (124) | +124.9% | 0.63 | 54% | −68% | +112% (Sharpe 0.34) |

Superficially the OOS is positive. Three things say don't believe it:

### 1. One period is the entire OOS result
- OOS total = **+45.3%**
- Single best fortnight (2025-07-07 → 2025-07-21) = **+49.4%**
- OOS total **excluding that one period = −4.1%**
- OOS **median** period = **−0.12%**; only **24/50** periods positive.

So the strategy did essentially nothing (slightly negative) for 49 of 50 OOS
periods and got one huge print. That is the definition of a fragile,
non-tradeable result, not an edge.

### 2. Beta dominated it out-of-sample
In the OOS window just holding the equal-weight basket returned **+164%**
(Sharpe 0.96) versus the long/short's +45% (Sharpe 0.48). The market ripped;
a dollar-neutral book gave up most of that. The long/short only looks good
*in-sample*, where the basket fell 52% and being market-neutral helped.

### 3. Huge drawdown
OOS max drawdown is **−68%** of the gross book. Even if the mean were real,
the risk profile is not something you'd run.

## What *is* real: the sign

The contrarian mirror (long high-DTC / short low-DTC) loses badly OOS
(−65%, Sharpe −0.69). So the direction is not random — high-days-to-cover
names did underperform low-days-to-cover names on average, matching the
informed-short-selling literature. The effect is directionally there; it's
just too weak, too concentrated in a couple of episodes, and too dominated by
market beta to trade in this form.

## Cost sensitivity (full sample)

| Cost/side | Total | Sharpe | Win rate |
|---|---|---|---|
| 0 bps | +149.7% | 0.76 | 57% |
| 5 bps | +124.9% | 0.63 | 54% |
| 10 bps | +100.1% | 0.51 | 52% |
| 20 bps | +50.5% | 0.26 | 49% |

Costs matter a lot because the book fully rebalances ~24×/year, but they are
not what kills it — the concentration and beta-dominance above do.

## Caveats that make even this flatter than reality

- **Survivorship bias**: the basket is names still liquid and listed *today*.
  High-short names that were acquired or delisted in 2021–2023 are absent, and
  those are disproportionately the ones the "short high-DTC" leg would have
  profited from *or* been squeezed by. Both the strategy and the benchmark are
  flattered.
- **Single fixed basket**: no universe reconstitution; IPO/SPAC names (RIVN,
  LCID, COIN, HOOD) simply enter when their data begins.
- **Days-to-cover, not %-float**: the free FINRA file has short position and
  ADV but not shares outstanding, so we couldn't test short-interest-%-of-float
  (arguably the cleaner cross-sectional signal).

## Verdict

Report it as a **no-edge / marginal** result. The signal's sign is real and
matches the literature, but in this basket and window it is not a tradeable
standalone strategy: the OOS profit is a single-period artifact, the median
period loses, and simply holding the basket beat it. The dry-run executor
exists to exercise the plumbing, deliberately gated off from ever trading.
