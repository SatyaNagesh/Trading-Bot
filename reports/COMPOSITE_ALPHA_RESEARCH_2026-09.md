# Composite Alpha Research Report (V3 — post-V2)

**Phase:** Composite Alpha Research V3 · **Date:** 2026-09-06
**Frozen pre-registration:** `data/alpha_v2/composite_freeze.json` v2 (v1 retained for audit) · v2 conditions revised per Phase 3 development-only conditional results
**Parent pre-registration:** V2 `reports/ALPHA_RESEARCH_V2_PREREG_2026-09.md` / `data/alpha_v2/feature_spec.json` (v1)
**Machine-readable results:** `reports/composite_alpha_results.json` · full tables: `data/alpha_v2/composite_{freeze,complementarity,conditional,eval}.json`

---

## 1. V2 survivor definitions (frozen, unchanged)

| Signal | Exact definition | Primary horizon | Classified (V2) |
|---|---|---|---|
| `C3_rev_abn_mkt1` | `ret(t) − index_ret(t)` (index = equal-weight universe excluding latest listing); causal at t | 1d | B. PROMISING (reversal) |
| `G1_breadth_rise` | fraction(symbols with `ret(t) > 0`); date-level | 3d | B. PROMISING (timing) |
| `G6_breadth_mom5` | `G1(t) − G1(t−5)`; date-level | 3d | B. PROMISING (timing) |
| `G4_xs_ret_disp` | cross-sectional `std(ret(t))`; date-level | 1–5d | B. PROMISING (timing) |

Recorded V2 evidence (frozen in `composite_freeze.json`): C3 final-fed holdout IC −0.020 (p=.008); G1|3 holdout-val +0.109 (p=.007); G6|3 holdout-val +0.121 (p=.003); G4|1–5 holdout-val +0.10–0.15. Definitions/formulas/windows are not altered by anything in this phase.

## 2. Complementarity (Phase 2; development only)

**Row-level correlation** (all split + symbol × date rows):

| Pair | Pearson | Spearman | Verdict |
|---|---|---|---|
| C3 ↔ G1 | ≈ 0.00 | ≈ −0.02 | independent |
| C3 ↔ G6 | ≈ −0.01 | ≈ −0.02 | independent |
| C3 ↔ G4 | ≈ 0.00 | ≈ −0.01 | independent |
| G1 ↔ G6 | 0.713 | 0.706 | **redundant** (G6 is the 5-day change of G1) |
| G1 ↔ G4 | 0.026 | 0.029 | independent |
| G6 ↔ G4 | 0.058 | 0.047 | independent |

**Prediction-level** (date-mean of −C3 score vs date-level G): Spearman +0.06–0.08 for breadth, +0.02 for dispersion — effectively orthogonal. The G-features are date-level constants, so additive/rank combinations with a cross-sectional reversal rank are **vacuous** (they cannot change per-date ordering); the only meaningful combination is the **conditional filter**, which is the method frozen here (Phase 6, option 3).

**Observation overlap:** breadth-stress gates 37.6% of dates, high-dispersion 41.9%, joint 14.9%; the bottom-10% reversal-relevant days land in these bins at proportionally similar rates (37%/62%/22%).

## 3. Conditional analysis (Phase 3; development only, pre-specified bins)

Reversal IC (`C3` vs `fwd_ret`, pooled development) inside a priori bins:

| Bin | h=1 IC | h=3 IC | h=5 IC | Read |
|---|---|---|---|---|
| Breadth high (≥ median) | −0.016 | −0.022 | −0.018 | weaker |
| Breadth low (< median) | **−0.028** | −0.030 | −0.025 | ~2× stronger |
| Breadth rising (G6≥0) | −0.017 | −0.024 | −0.018 | weaker |
| Breadth falling (G6<0) | **−0.029** | −0.030 | −0.025 | ~2× stronger |
| Dispersion high (≥ median) | **−0.025** | −0.031 | −0.027 | stronger |
| Dispersion low (< median) | −0.020 | −0.021 | −0.015 | weaker |

**Reversal concentrates in weak/falling-breadth and high-dispersion regimes.** This is the development-only evidence that drove the composite freeze (phase 3 → 4 sequence). No holdout data were consulted.

## 4. Pre-registered composites (Phase 4; frozen before any evaluation)

Score = `−C3_rev_abn_mkt1` (positive = stronger reversal candidate), applied **only on dates satisfying the gate** (else NaN/flat). Thresholds = **dev-TRAIN date-level medians**, frozen: `G1|3 ≥ 0.5104` · `G6|3 ≥ 0` · `G4|1 ≥ 0.01522`.

| Composite | Condition (frozen) | Method | Coverage (dev) |
|---|---|---|---|
| **COMP1 Reversal+Breadth** | `G1 < 0.5104 AND G6 < 0` (weak + falling breadth) | conditional filter | 40% of dates |
| **COMP2 Reversal+Dispersion** | `G4 ≥ 0.01522` (high dispersion) | conditional filter | 42% |
| **COMP3 Reversal+Breadth+Dispersion** | both COMP1 and COMP2 conditions | conditional filter | 15% |

Each has a mirror "inverse" gate pre-registered as a symmetric diagnostic (reported, never selected). **Version note:** the initial freeze gated the constructive regimes; Phase 3 development results showed reversal is stronger in stress regimes, so conditions were revised to the stress side **before any composite evaluation** (v2). Thresholds, horizons, weights, methods unchanged; only the sign of the gate changed, on development information — consistent with the mandated P3→P4 ordering.

## 5. Development results (Phase 5–7; three dev windows)

| Composite | split | n | h=1 IC | p | h=3 IC | h=5 IC | Q5−Q1 spread |
|---|---|---|---|---|---|---|---|
| **C0 baseline** (always-on) | train | 106,855 | +0.0217 | 1e-12 | +0.0265 | +0.0222 | 0.03% |
| | validation | 30,086 | +0.0286 | 7e-07 | +0.0287 | +0.0166 | 0.06% |
| | final-OOS | 14,503 | +0.0215 | 9.6e-03 | +0.0184 | +0.0233 | 0.05% |
| **COMP1** | train | 38,829 | +0.0302 | 2.7e-09 | +0.0300 | +0.0263 | 0.07% |
| | validation | 11,907 | **+0.0372** | 4.8e-05 | +0.0323 | +0.0191 | 0.09% |
| | final-OOS | 6,124 | **+0.0444** | 5.1e-04 | +0.0397 | +0.0347 | 0.14% |
| **COMP2** | validation | 6,811 | +0.0140 | 0.25 (ns) | +0.0372 | +0.0354 | 0.07% |
| | final-OOS | 3,185 | +0.0424 | 1.7e-02 | +0.0143 | +0.0330 | 0.16% |
| **COMP3** | train | 18,701 | +0.0411 | 2e-08 | +0.0363 | +0.0310 | 0.11% |
| | validation | 2,695 | +0.0289 | 0.13 (ns) | +0.0332 | +0.0404 | 0.17% |
| | final-OOS | 1,225 | **+0.0762** | 7.6e-03 | +0.0596 | +0.0753 | — |

**COMP1 lifts dev rank-IC ~1.3–2.1× over the always-on baseline at h=1 (0.030 → 0.037 → 0.044 across train → validation → final-OOS), and is consistent at h=3 and h=5. COMP2 does **not** improve on the validation window (0.014 vs baseline 0.029) — the dispersion gate alone is not a reliable complement. COMP3 shows the highest IC overall and, critically, its inverse gate is nil (+0.015, ns) — the joint stress gate concentrates the effect — but its coverage is thin (8% of final-OOS rows) and validation is underpowered (ns).**

## 6. Cross-sectional tests (Phase 8)

Per-date ranking -> quintiles on gated dates:

- **COMP1 validation:** long−short +0.8bp/day (t=0.10), 55% positive days; final-OOS +6.6bp/day (t=0.60), 54% positive; long excess vs market +2.2% (val) / +8.5% (final, cum).
- **COMP3 validation:** Q5−Q1 17bp/day, long−short +15.3bp/day (55 rebalances), net of 25bps **+10.2%** (2.5y, thin calendar).
- The spread is small per day for COMP1 — the composite's edge shows in rank-IC strength and in the cost-adjusted tail (below), not in fat daily decile spreads.

## 7. Holdout contamination status (Phase 14)

- **Frozen 60-symbol holdout: CONSUMED** by V2 — cannot be reused as evidence for this composite.
- **holdout_2: LOCKED** for V1 transform confirmation (lock `11c5eff3…`) — not reusable.
- No other corpus is in hand. **Confirmation requires a NEW, untouched holdout-3 evaluated ONCE** under the frozen protocol (below). This report therefore cannot grade anything above B.

## 8–11. Robustness (Phase 9–11; development)

**Tail fragility (h=1, validation):** all variants improve together, consistent with day-to-day mean reversion rather than extreme-driver dependence:

| | full | winsorized 1% | drop 1% | drop 5% |
|---|---|---|---|---|
| C0 | 0.029 | 0.029 | 0.034 | 0.041 |
| COMP1 | 0.037 | 0.037 | 0.041 | **0.049** |
| COMP3 | 0.029 | 0.029 | 0.035 | 0.042 |

IC is *higher* after tail removal — the signal is not carried by outlier days. (The earlier STRONG caveat stands from V2: the **decile-spread** version of raw C3 is tail-unstable across universes — this phase does not rescind that.)

**Symbols (validation):** COMP1: 69% of symbols positive, median symbol IC +0.039 (baseline 76% positive, median +0.023). Not one-sector/few-symbol driven.

**Regimes (validation):** COMP1 positive in 8/9 regime buckets, strongest in `down|low_vol` (+0.081), `sideways|med_vol` (+0.060), `up` (weakest) — consistent with a stress/rotation tilt.

**Temporal:** COMP1 positive in **10/10** half-year bands (median band IC +0.036); baseline 23/25 bands. Stable through the full dev history.

## 12. Cost-aware diagnostic (Phase 12; 25 bps/side primary, 15/50 sensitivity, 10% deciles, rebalance daily)

| Composite | split | gross | net @15 | net @25 | net @50 | turnover |
|---|---|---|---|---|---|---|
| C0 (baseline) | train | −22.6% | −22.8% | −23.0% | −23.3% | <0.01 |
| | validation | −39.2% | −39.3% | −39.5% | −39.8% | <0.01 |
| | final | −3.0% | −3.3% | −3.5% | −4.0% | 0.007 |
| **COMP1** | train | +58.4% | +57.9% | +57.6% | +56.9% | 0.003 |
| | validation | +2.2% | +1.9% | **+1.7%** | +1.1% | 0.008 |
| | final-OOS | +8.9% | +8.5% | **+8.3%** | +7.8% | 0.016 |
| **COMP3** | train | +31.6% | +31.2% | +31.0% | +30.3% | 0.005 |
| | validation | +10.7% | +10.4% | **+10.2%** | +9.6% | 0.036 |
| | final-OOS | +4.3% | +4.0% | +3.8% | +3.2% | 0.080 |

**The gate is the whole difference:** raw reversal is *cost-negative* on dev in decile form, while COMP1/COMP3 are net-positive in every dev window at all cost assumptions. But COMP1's validation net (+1.7% over 2.5y) is economically marginal — enough to justify research persistence, not a strategy.

## 13. Randomization (Phase 13; within-symbol permutation of C3, score rebuilt under fixed gate)

| Composite | obs IC | null mean | null σ | p (two-sided) |
|---|---|---|---|---|
| C0 | +0.0229 | −0.0001 | 0.0027 | 0.000 |
| COMP1 | +0.0328 | −0.0001 | 0.0044 | 0.000 |
| COMP2 | +0.0253 | +0.0001 | 0.0042 | 0.000 |
| COMP3 | +0.0411 | −0.0002 | 0.0069 | 0.000 |

All composites sit >7 null-σ above zero. **Selection-bias caveat:** the composites were constructed from V2 survivors, so 0.05-level p is *weak* evidence; the permutation test cannot undo the selection that preceded it. The only remedy is holdout-3.

## 14–15. Final classification

| Composite | Grade | Basis |
|---|---|---|
| **COMP1 Reversal+Breadth** (weak/falling breadth, h=1) | **B. PROMISING — NEEDS HOLDOUT-3** | Dev rank-IC 0.030/0.037/0.044 (1.3–2.1× baseline), 100% positive temporal bands, permutation p=0, tail-robust, net-positive @25bps in every dev window; economic spread on validation still thin (~+2%/2.5y) |
| **COMP3 Reversal+Breadth+Dispersion** | **B. PROMISING — NEEDS HOLDOUT-3** (secondary) | Highest dev IC (+0.076 final), inverse-gate nil — but coverage ~15%, validation ns (underpowered); confirm only jointly with COMP1 |
| **COMP2 Reversal+Dispersion** | **D. REDUNDANT / NO INCREMENTAL VALUE** | Validation IC 0.014 ns, below baseline; dispersion alone does not condition reversal |
| C0 baseline | reference only | — |

**HOLD OUT-3 IS JUSTIFIED for COMP1** (and COMP3 as a secondary, drawn from the same corpus & protocol). Protocol frozen in `composite_freeze.json`: (i) acquire an untouched corpus **before** any evaluation; (ii) evaluate COMP1/COMP3 **once** at h=1 under the frozen gates/thresholds; (iii) pass = sign-consistent IC ≥ 0.8 × dev-validation IC with 25bps net ≥ 0 and 10/10+ band consistency; (iv) only then Phase 15 strategy research. **No strategy, no paper trading, no AlphaLedger integration today; nothing here is promoted to a live system.**