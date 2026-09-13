# COMP3 STRATEGY V2 — Research Spec (diversified, frozen pre-holdout-5)

**Date:** 2026-09-13
**Status:** Binding spec. Frozen BEFORE the holdout-5 corpus is evaluated and
before any V2 trading. Supersedes nothing; `COMP3_STRATEGY_V1` remains the
immutable V1 baseline (`reports/COMP3_STRATEGY_SPEC_2026-09.md`).

Pre-registration + dev study: `reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md`
and `reports/COMP3_DIVERSIFICATION_RESEARCH_2026-09.md`.

---

## 1. Signal (unchanged from V1)
`COMP3_REVERSAL_BREADTH_DISP` score on date `t`:

    score(t) = -C3_rev_abn_mkt1(t)     on dates where gate(t) is ON
               NaN (no position)       otherwise

Gate and thresholds are identical to V1 (frozen in `composite_freeze.json` v2):
`G1_breadth_rise < 0.5104211897524967`, `G6_breadth_mom5 < 0`,
`G4_xs_ret_disp >= 0.015221737710112199`.

## 2. Signal timestamping / execution (unchanged)
- Signals use information through the close of `t`; entry at open of `t+1`,
  exit at close of `t+1`; daily session P&L = `close_{t+1}/open_{t+1} − 1`.
- Flat whenever gate is OFF. Same 25/50/100 bps cost stress as V1.

## 3. Constructions evaluated on holdout-5 (frozen)
Three constructions, all on the SAME frozen COMP3 score/gate:

| Name | Rule | Max single |w| | Rationale |
|---|---|---|---|---|
| `D1_CAP8` | top/bottom **13** names/side, EW 1/13 | 7.69% < 8% | **PRIMARY.** Pre-registered cap C=8%, chosen by the Amended dev-TRAIN rule (largest qualifying cap in {5,6,8,10}% with train top5_share<0.30 AND expectancy>0). Train top5 0.103, exp +8.66 bps. |
| `D2_QUINTILE` | top/bottom **8** names/side, EW 1/8 | 12.5% | Control: quintile equal weight (= V1 quintile). No cap. |
| `V1_DECILE` | top/bottom **4** names/side, EW 1/4 | 25% | V1 concentrated benchmark (decile). |

- `D1_CAP12` (C=12.5%, m=8) is weight-identical to `D2_QUINTILE`; it was reported
  on dev as an endpoint diagnostic and is EXCLUDED from the V2 primary definition
  (Amendment 1). It is NOT run on holdout-5 as a separate construction.
- Constructions are fixed and never re-selected from holdout data. The full
  candidate dev-TRAIN table (5/6/8/10/12.5%, winsorized windows, walk-forward,
  tail) is in `reports/COMP3_DIVERSIFICATION_RESEARCH_2026-09.md`.

## 4. That which changes vs V1
Only the position weighting/selection breadth changes (diversification):
- V2 PRIMARY `D1_CAP8` uses 13 names per side (max |w| = 7.69%) instead of V1's
  decile (4/side, 25%) or quintile (8/side, 12.5%).
- The comparison set is {D1_CAP8, D2_QUINTILE, V1_DECILE} on holdout-5.

## 5. Holdout-5 protocol (frozen)
- New untouched corpus `data/holdout_5/` (universe locked at commit `d6a26bf`,
  top-40 by marketCap, disjoint from all 228 previously-used symbols), single
  window 2014-01-01 → acquisition date, locked BEFORE evaluation.
- **One-shot:** run the three constructions once. No re-selection, no window
  tuning, no resampling after sight.
- Decision text: **A ROBUST DIVERSIFIED / B PROMISING-INSUFFICIENT /
  C SIGNAL SURVIVES-ECONOMICS FAIL / D STILL CONCENTRATION-FRAGILE /
  E FAILED TO REPLICATE / F COST-FRAGILE / G INCONCLUSIVE.** (Phase 12-14
  table in the pre-registration.)

## 6. Paper-trading gate (Phase 15)
`COMP3_STRATEGY_V2` may be paper-traded ONLY IF holdout-5 shows, on `D1_CAP8`
(primary): positive net expectancy, sufficient sample, acceptable drawdown,
acceptable concentration (top5_share < 0.30, no LOTO sign flips), positive under
realistic costs, temporal robustness, no leakage. ANY missing condition →
DO NOT PAPER TRADE. **NO live trading. NO AlphaLedger integration.**