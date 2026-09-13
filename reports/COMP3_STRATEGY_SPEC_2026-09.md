# COMP3 Strategy — Research Spec (Phase 1, frozen)

**Date:** 2026-09-08
**Status:** Binding spec, frozen BEFORE any strategy-level work executes.
**Review of prior signal evidence:** `data/alpha_v2/composite_freeze.json` (v2),
`data/alpha_v2/composite_eval.json`, `reports/COMPOSITE_ALPHA_RESEARCH_2026-09.md`,
`reports/HOLDOUT3_CONFIRMATION_2026-09.md`.

This document is the complete, pre-registered strategy design for the COMP3
composite signal (short-term reversal gated on joint market stress). It defines
everything the later phases (2-11 development study and 12 holdout-4
confirmation) must execute. Nothing in this spec may be changed after later
results are seen.

---

## 1. Signal (THE COMPOSITE)
`COMP3_REVERSAL_BREADTH_DISP` score on date `t`:

    score(t) = -C3_rev_abn_mkt1(t)        on dates where gate(t) is ON
               NaN (no position)          otherwise

- `C3_rev_abn_mkt1(t)` = `ret(t) − index_ret(t)`; index = equal-weight universe
  excluding the latest-listed symbol. Expected negative (short-term reversal),
  hence the sign flip in the score.
- Feature definitions are immutable (`data/alpha_v2/feature_spec.json` v1,
  `packages/research/alpha_v2_features.py`).

### Gate (joint market-stress)
```
gate(t) =  G1_breadth_rise(t)   <  g1_th
       AND G6_breadth_mom5(t)   <  0
       AND G4_xs_ret_disp(t)  >=  g4_th
```
- `g1_th = 0.5104211897524967`, `g4_th = 0.015221737710112199`
  (dev-TRAIN date-level medians, frozen in `composite_freeze.json` v2).
- These are the ONLY allowed use of the thresholds; no re-estimation.

## 2. Signal timestamping (no leakage)
- All inputs to score/gate use information through the CLOSE of `t`.
- Entry at OPEN of `t+1`; exit at CLOSE of `t+1` (1-day hold).
- Daily session P&L = `close_{t+1}/open_{t+1} − 1`.
- Positions rebalanced daily; flat whenever gate is OFF.

## 3. Constructions (exactly three in Phase 2-11; TWO on holdout-4)
- `decile_eq` — long top-decile / short bottom-decile, equal weight. (primary in dev)
- `quintile_eq` — long top-quintile / short bottom-quintile, equal weight.
- `rank_eq`? — NO. Rank/score aggregation beyond these is not defined.
- `decile_voladj` — volatility-adjusted weighting variant (dev diagnostics only).
- Holdout-4 evaluates ONLY `quintile_eq` (primary) and `decile_eq`
  (comparison); `decile_voladj` is excluded (numerically unstable in dev train)
  and shelved as a separate future experiment.

## 4. Costs
- Turnover: `2.0` at first deployment or when re-entering after an off-gate
  day; otherwise one-day `Σ|Δw|`.
- Net daily = gross − turnover × cost/side. Frozen levels: **25, 50, 100 bps/day.**
  All three reported for every construction; no cost level is chosen from results.

## 5. Phase plan
- Phase 2 (F02): signal interpretation — gate ON/OFF states, coverage, active-day
  forward-return behaviour.
- Phase 3 (F03): component attribution — pooled IC of COMP3 vs components vs
  baseline; quantile spread per construction; monotonicity.
- Phase 4 (F04): strategy backtest — all constructions × all cost levels, full
  metric sheet (active days, positions, turnover, gross/net, expectancy, PF,
  win rate, MDD, Sharpe, Sortino, worst/best period).
- Phase 5 (F05): statistical uncertainty — autocorrelation-adjusted effective
  n, block bootstrap CIs.
- Phase 6 (F06): walk-forward stability (4 contiguous windows, dev-timeline).
- Phase 7 (F07): bias & robustness diagnostics — sector/symbol/liquidity/date
  concentration surfaces (diagnosis only, no refit).
- Phase 12 (12A-12M): freeze + holdout-4 confirmation (separate doc
  `COMP3_STRATEGY_FREEZE_2026-09.md`).

## 6. Research rules
- DEVELOPMENT corpus only for Phases 2-11 (`data/alpha_v2/development_v2_panel.parquet`).
- Held-out corpora not used until the single holdout-4 confirmation run.
- No indicator explosion; only the frozen construction set above.
- No Kelly / RL / dynamic position sizing; equal weight only.
- All output JSONs written under `data/comp3/`; report to
  `reports/COMP3_STRATEGY_SPEC_2026-09.md` repo flow.

## 7. Integrity
Single pre-registered evaluation per construction. Report negative if negative.
No selection of parameters, cost levels, or windows after seeing any result.