# COMP3 Strategy — Freeze (Phase 12A)

**Date:** 2026-09-08
**Freeze baseline git commit:** `34e2e6420095a227efdeabbbdf7b4e93d1604254` (`main`)
**Research tag:** `research-freeze-2026-09-06` → `eb05d85e83dd0869816ee182a926345bbb674931`

This freezes the COMP3 strategy **exactly** as it will be run on holdout-4.
Nothing below changes after holdout-4 is seen (Phase 12B/12L/FINAL RULE).

---

## 1. Signal (COMP3 composite) — frozen
Score on date `t` = `-C3_rev_abn_mkt1(t)` evaluated **only** on dates where the
joint stress gate is ON; NaN (flat) otherwise.

- `C3_rev_abn_mkt1` = `ret(t) − index_ret(t)`, index = equal-weight universe
  excluding latest-listing symbol (expected negative IC → reversal ⇒ score −C3).
- `G1_breadth_rise` = `fraction(symbols with ret(1d) > 0)` at `t`.
- `G6_breadth_mom5` = `G1(t) − G1(t−5)`.
- `G4_xs_ret_disp` = cross-sectional `std(ret(1d))` at `t`.

### Gate (frozen)
```
COMP3_gate(t) =  G1_breadth_rise(t) < 0.5104211897524967
             AND G6_breadth_mom5(t) < 0
             AND G4_xs_ret_disp(t) >= 0.015221737710112199
```
Thresholds: development-TRAIN date-level medians from `composite_freeze.json` v2
(locked 2026-09-06). No re-estimation.

## 2. Signal timestamp
- Inputs ≤ close of `t` only (no `open_{t+1}`/`close_{t+1}` in the signal).
- Entry at **open of t+1**; exit at **close of t+1** (1-day hold).
- Session P&L = `close_{t+1}/open_{t+1} − 1`. Daily rebalance; flat when gate OFF.

## 3. Ranking & constructions (frozen — exactly two on holdout-4)
- **`quintile_eq` (primary)**: long top 20%, short bottom 20%, equal weight.
- **`decile_eq` (comparison)**: long top 10%, short bottom 10%, equal weight.
- **`decile_voladj` is EXCLUDED** from holdout-4 (numerical instability; shelved to
  a separate future research experiment). No weight optimization, no Kelly/dynamic
  sizing, no additional constructions after sight.

## 4. Costs (frozen)
- Turnover: `2.0` on first deployment or re-entry after off-gate day; else `Σ|Δw|`.
- Net daily = `gross − turnover × cost`. Frozen levels: **25, 50, 100 bps/day.**
  All three reported; no favoring a level after the result.

## 5. Evaluation matrix (Phases 12F-12K, automation in `holdout4_strategy.py`)
Per construction × cost: active days, portfolio obs, positions, turnover, gross,
costs, slippage, net, avg expectancy, median daily, profit factor, win rate, max
drawdown, Sharpe, Sortino, worst/best period.

Plus (diagnosis only): rolling windows, vol/market regimes, sector/symbol/liquidity/
market-cap; P&L contribution top-5/top-10; leave-one-symbol-out
(→ CONCENTRATION-FRAGILE); tail robustness (full/winsorized/extreme-influence);
statistical uncertainty (effective n, autocorrelation, block bootstrap, CI).

## 6. Decision rule (Phase 12M)
- **A CONFIRMED**: positive net expectancy@25bps, economically meaningful net return,
  adequate sample, acceptable DD, survives 25/50/100bps, no concentration failure,
  reasonable temporal stability, no leakage.
- **B PROMISING/INSUFFICIENT**, **C FAILED TO REPLICATE**, **D COST-FRAGILE**,
  **E CONCENTRATION-FRAGILE**, **F UNSTABLE**, **G INCONCLUSIVE**.

## 7. Paper-trading gate
Holdout-4 positive ⇒ create separate prospective candidate `COMP3_STRATEGY_V1`
(paper, no optimization). Never replaces `autonomous_momentum` directly. No
AlphaLedger integration, no live trading.

## 8. Integrity
Holdout-4 is a confirmation experiment, not an optimization environment. No
threshold/indicator/regime/weight/holding-period changes; no cherry-picking; no
reruns to force positivity; report negative if negative.

## 9. Data-availability note (Phase 12C)
The design frontier (dev + holdout-3) ends 2026-09-06. As of 2026-09-08 only ~2
trading sessions of chronologically-new data exist — **insufficient** for a 6-12
month strategy-level holdout (gate fires ~10% of days). See the Phase 12C
limitation note. The default acquisition window is the full pre-registered window
(`2014-01-01` → `2026-09-08`) on a new symbol-disjoint universe, evaluated as one
undivided sample; the exact window choice is recorded in the lock.