# Pre-Registration: vol_trend_10v50 Monetization Transforms + holdout_2

**Date:** 2026-09-06 · **Project:** VOL_TREND_SIGNAL_TO_ALPHA (Phase 8 step 1) · **Instrument:** `vol_trend_10v50 = SMA(volume,10)/SMA(volume,50) − 1`

---

## 1. Purpose

Phases 1–7, 11–13 (see `reports/vt_signal_diagnostics.json`) established that the
signal replicates a positive, significant Spearman IC in the independent holdout
(`final_oos` +0.015/@1d, +0.027/@3d) **but** that:

- the cross-sectional long–short decile spread is ≈ 0 on the holdout;
- the holdout IC is fully explained by cross-sectional exposures (beta, vol
  level, momentum, trend, size, liquidity): residual IC ≈ +0.003;
- quantile shapes (monotonic vs U) and regime signatures do not generalise
  across the two universes;
- the positive IC is a 2023+ phenomenon (window-level frac-positive ≈ 0.67 in
  OOS, ≈ 0.45 in 2014–2022).

This document pre-registers the *monetization* transforms (Phase 8) that will be
tested **once** on a **new untouched** universe (`holdout_2`) — held out of all
previous work — together with the exact gates and decision rule. It is written
**before** any holdout_2 data is downloaded and **before** any transform
evaluation. Nothing in the frozen pipeline (`9e70300`, `eb05d85`) is modified;
`data/holdout` (frozen) is **consumed** by the base-signal test and is **not**
used to validate transforms.

## 2. Central integrity rule

Any monetization of the signal is a **new hypothesis**. The frozen holdout
therefore cannot serve as its validation set. We:

1. **Pre-specify** the transforms, costs, and gates (this document + `data/holdout_2/transform_spec.json`).
2. Select a **return-independent** universe `holdout_2` (rule below).
3. Evaluate the pre-specified transforms on DEVELOPMENT-`validation` exactly as specified.
4. Run any transform passing the selection gate **exactly once** on `holdout_2`-`final_oos`.
5. Record all runs, including those that fail, verbatim.

## 3. Universe rule for holdout_2 (return-independent)

Implementation: `packages/research/select_holdout2_universe.py`

1. Candidate pool `CAND2` = the **remaining** frozen holdout-selection pool
   (tickers in `data/holdout/universe.json` `pool` that were neither selected into
   HOLDOUT nor dropped as resolution failures) **plus** a static supplementary
   list of 64 NSE mid/large-cap tickers (listed in the module).
2. Every candidate is asserted disjoint from DEVELOPMENT (49) and HOLDOUT (60).
3. Rank by Yahoo `fast_info['marketCap']` at the selection instant — no
   price-history returns are used.
4. Select **top 40** by market cap (ties alphabetized); unresolved tickers are
   dropped and logged — **no return-based substitution**.
5. Selected set is written to `data/holdout_2/universe.json` and may be the only
   source of symbols for the subsequent acquisition and evaluation.

The market-cap snapshot is a natural-history sampling rule (same accepted bias as
the frozen HOLDOUT universe).

## 4. Transform definitions (all daily-rebalanced, equal-weight, LS, market-neutral)

| ID | Construction |
|----|--------------|
| `T1_decile_raw` | long top-decile / short bottom-decile of raw cross-sectional rank |
| `T2_quintile_raw` | long top-quintile / short bottom-quintile of raw rank |
| `T3_decile_volstd` | deciles of feature scaled by per-symbol trailing 252d std (volume-scale neutralized) |
| `T4_decile_sector_relative` | deciles of within-date × within-sector rank (sector-balanced) |
| `T5_decile_neutralized` | deciles of per-date rank-OLS residual of the feature on rank(beta, vol, mom, trend, size, liq) |

## 5. Costs

- Primary: **25 bps per side** (brokerage + realistic impact).
- Sensitivity: **15 bps per side** (frozen pipeline base cost) — reported for
  transparency; primary decision uses 25 bps.

## 6. Selection gate (DEVELOPMENT `validation`)

A transform is **SELECTED** for holdout_2 confirmation iff, on development
`validation`:
- net (25 bps) LS mean daily return > 0, **and**
- 95% block-bootstrap CI (block = 63 days, 1000 sims, seed 7) lower bound > 0,
- then BH-FDR (Benjamini–Hochberg) **q ≤ 0.10** across the five transforms.

p-value = fraction of bootstrap sims with mean ≤ 0.

## 7. Confirmation (holdout_2 `final_oos`, exactly one run)

A selected transform is **MONETIZABLE** iff its single holdout_2-`final_oos` run
satisfies net (25 bps) mean > 0 **and** 95% CI lower > 0.

If nothing passes the gate, we record “not monetizable at any pre-specified
construction” and proceed to the A–G classification in the final report with
`honest verdict`, no forced strategy.

## 8. Deliverables of this phase

- `data/holdout_2/transform_spec.json` (machine-readable spec)
- `data/holdout_2/universe.json` (selected universe + snapshot)
- `data/holdout_2/manifest.json`, `audit*`, `splits.json`, `dataset_lock.json`
- `packages/research/vt_transforms.py` (evaluator reading the spec)
- `reports/vt_transforms_results.json` (all runs, gate + confirmations)
- Final: `reports/VOL_TREND_SIGNAL_TO_ALPHA_2026-09.md` + `.json` (P14 classification)