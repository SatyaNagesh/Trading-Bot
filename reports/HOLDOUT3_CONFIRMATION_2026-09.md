# Composite Alpha V3 — Holdout-3 Confirmation (2026-09)

One-shot evaluation of the frozen composites COMP1 and COMP3 on a NEW, untouched
corpus. Protocol frozen in `data/alpha_v2/composite_freeze.json` (v2). Grades
drawn strictly from the pre-registered rule; no post-hoc adjustments.

## 1. Corpus provenance (untouched)

- **Selector:** `packages/research/select_holdout3_universe.py` — pre-registered,
  return-independent rule: top-40 by Yahoo `fast_info['marketCap']` snapshot from
  a static tranche-3 NSE pool, disjoint from DEVELOPMENT (49), HOLDOUT (60),
  HOLDOUT_2 (39). Overlap guard auto-excluded 1 symbol (`TATACOMM.NS`); failures
  dropped without substitution. `universe.json` written BEFORE any download.
- **Acquisition:** `packages/research/acquire_holdout3.py` — frozen
  ingestion/audit, store root `data/holdout_3`. 40/40 downloaded
  (2010-01-04 -> 2026-09-04), 1 purged (JBCHEPHARM empty-after-cleanse),
  **38 eligible** (bars>=700), 1 dropped (`EMCURE.NS`, 533 bars).
- **Lock:** `manifest.json` sha256 `98fb2f57…`, `dataset_lock.json` written.
  Splits verbatim (train 2014-01-01 / validation 2023-01-01 / final-oos
  2025-07-01). 2014+ retained rows: **101,710**.
- **Features:** frozen `alpha_v2_features` builders applied to the corpus
  (`build_holdout3_panel.py`); G-features are date-level (own-universe).

## 2. Method (verbatim from composite_freeze.json v2)

- Composites: score = `−C3_rev_abm_mkt1` gated by date-level conditions.
  - COMP1 = `(G1_breadth_rise < 0.5104) AND (G6_breadth_mom5 < 0)`
  - COMP3 = COMP1 AND `(G4_xs_ret_disp >= 0.01522)`
- Thresholds: dev-TRAIN date-level medians (frozen; never recomputed).
- Evaluation: h=1 primary; method parity = `eval_composite` from
  `composite_alpha.py`; verification of dates per composite: COMP1 1162/3124
  (37.2%), COMP3 973/3124 (31.1%).
- Pass rule (strict): **sign-consistent pooled rank-IC(h=1) ≥ 0.8 × the
  composite's own dev-VALIDATION IC, AND net@25bps ≥ 0, AND majority-positive
  126d bands.**

## 3. Results (holdout-3, pooled 2014+)

| | C0 baseline | **COMP1** | **COMP3** | COMP1 inverse |
|---|---|---|---|---|
| **pooled rank-IC (h=1)** | +0.0270 | **+0.0295** | **+0.0291** | +0.0228 |
| p | 6.9e-18 | 1.0e-08 | 2.3e-07 | ~0 |
| dev-VALIDATION IC (ref) | 0.0286 | 0.0373 | 0.0289 | — |
| strict threshold 0.8×own | — | **0.0298** | **0.0232** | — |
| net @25bps (whole corpus) | −68.7% | **+67.5%** | **+30.7%** | — |
| gross @25bps (whole corpus) | −68.7% | +67.5% | +30.7% | — |
| temporal bands (+ / total) | 24/25 | **10/10** | **8/8** | 13/16 |
| within-symbol permutation p | 0/200 | 0/200 | 0/200 | 0/200 |
| per-period net @25bps (train/val/final) | −68/−37/+53% | −4.7/+19.6/+45.5% | −20.8/+18.1/+38.3% | — |

Per-split IC (COMP1): train +0.0296 (p<1e-3), validation +0.0205 (p=0.066, ns),
final-OOS +0.0472 (p=0.002). (COMP3): train +0.0285, validation +0.0197
(p=0.096, ns), final-OOS +0.0583 (p=0.001). Sign is consistent in every window;
validation windows are individually underpowered.

## 4. Verdicts (strict, pre-registered rule)

| Composite | pooled IC ≥ 0.8×own dev-val IC | net @25 ≥ 0 | bands | Verdict |
|---|---|---|---|---|
| **COMP1** Reversal+Breadth | 0.0295 < 0.0298 (**MISS by 0.0003**) | PASS | PASS | **FAIL (marginal)** |
| **COMP3** Reversal+Breadth+Disp | 0.0291 ≥ 0.0232 (**PASS**) | PASS | PASS | **PASS** |

- **COMP3 — CONFIRMED on holdout-3.** Replicates out-of-sample with the frozen
  gate; net-positive at 25bps in every 2014+ window; 8/8 positive half-year
  bands; permutation p 0/200. Grade per the pre-registered scale:
  **A (CONFIRMED)** — subject to the caveats in §5.
- **COMP1 — replicated but fails the strict IC bar by 0.0003.** Statistically
  unambiguous (pooled p≈1e-8, permutation 0/200, 10/10 bands, net +67%) yet the
  letter of the frozen rule says IC 0.0295 < 0.0298. **Stays B.** Note: against
  the baseline-relative reading (0.8 × C0 dev-val = 0.0229) COMP1 would PASS;
  the strict reading is retained to avoid precedent-setting round-ups.
- **COMP2** — unchanged: D / no incremental value.

## 5. Caveats (honest limits of the confirmation)

1. **Universe tilt:** holdout-3 selects mid/small-cap names (INDHOTEL, MAZDOCK,
   OFSS, AUBANK, …) where day-scale mean reversion is structurally stronger than
   in the large-cap dev universe. Part of the replicated effect is a population
   tilt, not proof the feature is as strong on large caps.
2. **Thin cross-section:** 38 symbols → 10% deciles = ±3-4 names per leg; the
   backtest is idiosyncratic, not a diversifiable Nifty implementation.
3. **Validation windows individually ns** for both composites (p≈0.07-0.10);
   significance comes from pooling over 12.5y and the strong 2025-26 final window.
4. **Raw C3 decile economics remain fragile** (C0 net −69% on this corpus while
   its rank-IC is +0.027) — the gate, not the signal alone, produces the
   economics; this confirms COMP-style deployment, not naked reversal.
5. **Gate lift shrinks on this universe:** COMP1 confirm +0.0295 only ~+0.007
   above C0 (+0.0270); the inverse gate also shows +0.0228. Economic lift of the
   gate (net) is nonetheless large.
6. One-shot evaluation, no re-runs, no threshold tuning — per protocol.

## 6. Status / next

- COMP3 = **A (CONFIRMED)** is a *research* result: pre-registered, held out, once
  evaluated. **No paper/paper-trading/AlphaLedger integration and no live
  strategy** — the frozen Phase-15 rule gates those behind an explicit user
  decision.
- COMP1 retains B (strict fail); if the user accepts the baseline-relative
  reading of the pass rule, its status can be revisited with this corpus as the
  evidence — noted here, not applied.
- Phase 15 (strategy research on confirmed COMP3) is optional and a new scope:
  capital, leverage, universe persistence, slippage model — recommend a separate
  decision before starting.

## Files

- `data/holdout_3/`: universe.json, manifest.json, quarantine.json, audit.json,
  eligible_symbols.json, splits.json, dataset_lock.json, alpha_panel_holdout3.parquet
- `data/alpha_v2/holdout3_v2_panel.parquet` — V2 feature panel (45 key + carry)
- `data/alpha_v2/holdout3_eval.json` — full per-split/per-cost/temporal/permutation
- `packages/research/select_holdout3_universe.py`, `acquire_holdout3.py`,
  `build_holdout3_panel.py`, `composite_holdout3.py`