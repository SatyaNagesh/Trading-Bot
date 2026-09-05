# Deep Validation — `vol_rel20@1`

**Project:** Alpha Discovery Engine → Deep Validation phase
**Feature under test:** `vol_rel20` = short-term (realized) vol ÷ long-term (realized) vol, 20-day lookbacks ("volatility expansion ratio")
**Signal rule (FIXED, no parameters selected from outcomes):** every trading day rank eligible symbols by `vol_rel20`, LONG top decile, SHORT bottom decile, equal weight, rebalance daily.
**Cost model (base):** 0.05% commission + 0.10% slippage per side = 0.15% per side.
**Report date:** 2026-09-05 · **Machine-readable:** `reports/volatility_alpha_validation.json`

**FINAL DECISION: F. UNSTABLE — NO REPRODUCIBLE ALPHA DEMONSTRATED.**

> Status of the +29.9% figure: it is **DISCOVERY evidence**, produced by a 105-hypothesis screen whose FINAL-OOS window was scored once. Under confirmation testing it does **not** reproduce reliably, is **not** distinguishable from chance (p ≈ 0.08–0.09), and its profitability is **concentrated in a recent stress sub-period**.

---

## Answer summary (the 9 questions)

| # | Question | Answer |
|---|---|---|
| 1 | Survives across time? | **NO** — 10/21 six-month OOS windows net-positive (48%); avg +3.2% but σ = 13.6%/window; positives cluster in high-vol/stress windows |
| 2 | Works across many symbols? | **Weakly** — 29/49 symbols positive (59%); top-5 symbols = 60% of total net; median per-symbol IC ≈ 0.001 |
| 3 | Survives regimes? | **NO** — regime ICs sign-flip between TRAIN/VALIDATION and OOS (e.g. `sideways|high_vol` +0.035 → **−0.142**); coherent only in parts |
| 4 | Monotonic? | **NO** — TRAIN U-shaped, VALIDATION flat, FINAL-OOS outlier-driven top bucket only |
| 5 | Outlier-dependent? | **NO** — dropping top-1% extreme labels retains ~80% of net (23.99/29.85) |
| 6 | Survives costs/slippage? | **YES** — turnover trivial (p50≈0.0), drag 0.39% vs +30.2% gross; positive even at 2× costs |
| 7 | Beats randomized controls? | **NO** — all three nulls p_two-sided ≈ 0.083–0.093 (> 0.05) |
| 8 | Untouched chronological holdout? | **NOT AVAILABLE** — corpus ends 2026-09-04; every slice was used at least once. Frozen last-252d rerun (+40.2%) is disclosed as tainted, not confirmatory |
| 9 | Strong enough for a strategy? | **NO — DO NOT TRADE.** See recommendation |

---

## 1. Why F (not A/B/D)

- The decisive confirmatory test (randomization on the very window that produced the claim) fails: observed daily-long-short mean +0.0957% vs null mean +0.006…0.010% (sd ≈ 0.054%), p_two-sided = 0.083/0.087/0.093. Never < 0.05.
- Temporal replication is a coin flip (48% positive windows) with great variance.
- The effect is **state-dependent**: net profits concentrate in high-volatility/stress windows (COVID 2020 window +26.7%, 2024-09→2025-03 +16.9%, 2025-09→2026-04 +22.2%) and it bleeds in calm periods (2015–2016, 2021–2024 several −5…−11% windows). A state-dependent effect can be *described* as "regime-specific" (D), but the confirmatory statistics do not survive the chance-contrast **anywhere**, so the honest classification is **UNSTABLE**: information present is real-or-chance, but not reproducible enough to claim alpha.

---

## 2. Phase 2 — Full temporal replication (21 × 6-month OOS windows)

Expanding walk-forward: each window = full history as TRAIN, then 6m VALIDATION, then 6m OOS. No hyperparameters exist to select (rule fixed), so OOS is measured directly. Metrics on the OOS slice only.

| window (val start) | OOS ic | daily LS % | net after costs % |
|---|---|---|---|
| 2015-01-07 | −0.0131 | −0.2206 | **−25.24** |
| 2015-07-13 | +0.0459 | −0.0872 | −11.35 |
| 2016-01-15 | +0.0031 | −0.0774 | −10.47 |
| 2016-07-21 | −0.0042 | −0.0891 | −11.53 |
| 2017-01-24 | +0.0125 | +0.0956 | +16.21 |
| 2017-07-28 | −0.0033 | −0.0241 | −4.11 |
| 2018-01-30 | −0.0075 | +0.0383 | +3.42 |
| 2018-08-01 | +0.0191 | +0.1376 | +17.56 |
| 2019-02-06 | −0.0085 | −0.0355 | −5.47 |
| 2019-08-16 | −0.0543 | +0.2141 | +26.75 (COVID) |
| 2020-02-19 | +0.0259 | +0.1061 | +12.55 |
| 2020-08-25 | +0.0095 | +0.0898 | +10.41 |
| 2021-02-23 | +0.0000 | +0.1435 | +18.37 |
| 2021-08-30 | −0.0134 | −0.0343 | −5.21 |
| 2022-03-02 | +0.0186 | +0.0010 | −1.96 |
| 2022-09-05 | −0.0036 | +0.1212 | +15.18 |
| 2023-03-06 | +0.0099 | −0.0554 | −7.66 |
| 2023-09-08 | +0.0215 | −0.0299 | −6.28 |
| 2024-03-15 | +0.0785 | +0.1335 | +16.85 |
| 2024-09-20 | +0.0050 | −0.0162 | −2.81 |
| 2025-03-24 | +0.0002 | +0.1674 | +22.20 |

**Aggregate:** positive-net in 10/21 (48%), avg +3.21%, σ 13.60%, median daily LS +0.001%. **The signal does not survive repeatedly over time**; it is profitable in bursts tied to high-volatility states.

---

## 3. Phase 3 — Cross-sectional shape (do NOT assume high vol is better)

Daily-aggregated quintile means of next-day returns (Q1 = lowest `vol_rel20` … Q5 = highest):

| split | shape | Q1 | Q2 | Q3 | Q4 | Q5 | spread |
|---|---|---|---|---|---|---|---|
| TRAIN | **u_shaped** | 0.0946 | 0.0831 | 0.0896 | 0.0815 | 0.1083 | +0.0137% |
| VALIDATION | **unstable** | 0.0983 | 0.1028 | 0.0766 | 0.0781 | 0.0952 | −0.0031% |
| FINAL-OOS | **outlier_driven_top** | −0.0008 | −0.0046 | 0.0228 | 0.0056 | 0.0615 | +0.0623% |

The relationship is **not** monotonic. TRAIN is a U (both tails high), VALIDATION is flat, and FINAL-OOS is driven by the extreme Q5 bucket alone (Q5 0.0615 vs Q4 0.0056). The decile-level detail (JSON `quantile_shape`) confirms: the FINAL-OOS edge sits almost entirely in the top decile's biggest spread. No consistent "top is better" ranking exists.

---

## 4. Phase 4 — Symbol robustness (FINAL-OOS)

- 29/49 symbols (59%) have positive net contribution; median per-symbol IC 0.001; per-symbol hit-rate ≈ 0.50–0.55.
- Concentration: **top-1 symbol = 21.3%**, **top-5 = 60.2%** of total net (+28.0%); HHI on absolute contribution 0.031 (low, i.e. spread across names, but five names carry the bulk of the profit).
- The +29.9% is **not** a one-symbol fluke (no single name > 22% share), but it is materially concentrated in ~5 names. Not disqualifying, not reassuring.

---

## 5. Phase 5 — Regime robustness (no regime strategy is constructed)

`regime_bucket` = market direction × volatility bucket, IC (daily LS in %) on TRAIN+VALIDATION vs FINAL-OOS:

| regime | t/v IC | t/v LS% | oos IC | oos LS% |
|---|---|---|---|---|
| down\|high_vol | +0.0099 | +0.036 | +0.0051 | −0.020 |
| down\|low_vol | +0.0084 | −0.006 | −0.0545 | −0.072 |
| down\|med_vol | +0.0615 | +0.231 | +0.0669 | — (n small) |
| sideways\|high_vol | +0.0348 | −0.012 | **−0.1424** | −0.276 |
| sideways\|low_vol | +0.0191 | −0.047 | +0.0401 | +0.152 |
| sideways\|med_vol | +0.0036 | +0.064 | +0.0277 | +0.259 |
| up\|high_vol | +0.0027 | +0.074 | +0.0614 | +0.237 |
| up\|low_vol | −0.0083 | +0.005 | −0.0363 | +0.159 |
| up\|med_vol | +0.0051 | −0.014 | +0.0759 | −0.054 |

Sign agreement 7/9 buckets, but the relationship is **incoherent**: the largest positive train/validation IC buckets invert at OOS (`sideways|high_vol` +0.035→−0.142; coarse market-regime `up|med_vol` −0.003→+0.063) and daily LS signs disagree with IC signs in half the rows. No regime family is consistently predictive.

---

## 6. Phase 6 — Outlier / concentration

FINAL-OOS long/short under label perturbations:

| variant | daily LS % | quintile spread % | net after costs % |
|---|---|---|---|
| full | 0.0959 | 0.0623 | 29.851 |
| drop top-1 by abs | 0.0725 | 0.0497 | 21.476 |
| drop top-5 by abs | 0.0725 | 0.0414 | 21.476 |
| drop top-1% by abs | 0.0784 | 0.0619 | 23.991 |
| winsorize 1/99 | 0.0836 | 0.0546 | 25.775 |

**NOT OUTLIER-DEPENDENT**: dropping the top 1% of extreme labels retains ~80% of net (23.99/29.85). The effect is not an artifact of a handful of monstrous days.

---

## 7. Phase 7 — Horizon curve (report the complete curve; do not pick the best)

FINAL-OOS, IC and daily long-short by horizon:

| horizon | 1d | 2d | 3d | 5d | 10d | 20d |
|---|---|---|---|---|---|---|
| IC | +0.0074 | +0.0145 | −0.0019 | +0.0009 | +0.0476 | +0.0706 |
| LS %/day | 0.096 | 0.086 | 0.016 | 0.33 | 0.71 | 0.91 |
| LS t | 1.57 | 0.61 | 0.08 | 1.15 | 1.25 | 0.82 |

**No coherent decay**: the 1–3d relation vanishes (3d IC negative), then LS grows at 5–20d with weak t-stats and IC ≈ 0 at 5d. A true relationship would show a monotone, interpretable decay — this is noise-like and discontinuous (the "best" 10d/20d numbers are exactly the kind of post-hoc picks this project forbids).

---

## 8. Phase 8 — Alternative volatility definitions (small, pre-specified family)

Family = {`vol_rel20`, `vol_pctile_252`, `vol_atr_pct`, `vol_trend_10v50`, `vol_realized20`} × {1,3,5}d = 15 hypotheses; BH-FDR on VALIDATION q≤0.10:

| feature | horizon | val IC | FDR q |
|---|---|---|---|
| **vol_rel20** | 1 | +0.0288 | **0.0000** |
| **vol_rel20** | 3 | +0.0216 | **0.0014** |
| **vol_rel20** | 5 | +0.0215 | **0.0053** |
| **vol_trend_10v50** | 1 | +0.0155 | **0.0258** |
| **vol_trend_10v50** | 3 | +0.0201 | **0.0258** |
| vol_pctile_252 | 1 | +0.0089 | 0.232 |
| vol_pctile_252 | 3 | +0.0126 | 0.214 |
| vol_pctile_252 | 5 | +0.0119 | 0.286 |
| vol_atr_pct | 1–5 | 0.002–0.008 | 0.28–0.84 |
| vol_realized20 | 1–5 | 0.0025–0.0045 | 0.73–0.83 |

Interpretation: **the *ratio* construct (short÷long vol, i.e. vol expansion) — `vol_rel20` and its sibling `vol_trend_10v50` — has validation-level signal; volatility *level* features do not.** This is the strongest quasi-independent corroboration the signal family earns. It does not rescue reproducibility at OOS (Phase 2/3/10).

---

## 9. Phase 9 — Cost / turnover

Turnover is tiny (p50 ≈ 0.0, mean 0.003–0.007/day; the top/bottom decile membership barely changes daily).

| period | cost/side | gross | drag | net |
|---|---|---|---|---|
| VALIDATION | 0.15% | +21.93% | 0.37% | +21.56% |
| VALIDATION | 0.20% | +21.93% | 0.50% | +21.44% |
| VALIDATION | 0.25% | +21.93% | 0.62% | +21.31% |
| VALIDATION | 0.30% | +21.93% | 0.75% | +21.19% |
| FINAL-OOS | 0.15% | +30.24% | 0.39% | +29.85% |
| FINAL-OOS | 0.20% | +30.24% | 0.52% | +29.72% |
| FINAL-OOS | 0.25% | +30.24% | 0.65% | +29.59% |
| FINAL-OOS | 0.30% | +30.24% | 0.78% | +29.46% |

**NOT cost-fragile** at this horizon. Costs are a secondary concern for this signal; reproducibility/state-dependence is the primary one.

---

## 10. Phase 10 — Randomization controls

FINAL-OOS daily long-short mean, observed +0.0957%/day, tested against 300-simulation nulls:

| null | mean | sd | p_two-sided |
|---|---|---|---|
| shuffle feature (within symbol) | +0.0096% | 0.054% | 0.0833 |
| random ranking (per date) | −0.0038% | 0.053% | 0.0867 |
| shuffle labels (within symbol) | +0.0065% | 0.056% | 0.0933 |

**The observed effect is not distinguishable from chance** at the 5% level (all nulls p ≈ 0.08–0.09). Marginal at best.

---

## 11. Phase 11 — Selection-bias audit (DISCOVERY vs CONFIRMATION)

- **DISCOVERY:** `vol_rel20@1` came from a **105 (feature×horizon) screen**: 54 sign+magnitude pre-selected, BH-FDR on VALIDATION → 31 survivors including `vol_rel20@1` (and `@3`). The FINAL-OOS window was scored once to produce +29.9%; it is **not** a fresh holdout.
- **CONFIRMATION (this run):** fixed rule, no parameters to select, TRAIN/VALIDATION/OOS windows, randomization, cost ladder, symbol/regime robustness. All statistics below are **conditional on survival of the screen** and therefore conservative when they fail, optimistic when they pass.
- Every p-value here is pre-experimental; treat the near-miss randomization p-values with the prior of "discovered among 105" firmly in mind.

---

## 12. Phase 13 — no strategy constructed

No `autonomous_momentum` change, no production/paper strategy, no threshold or entry/exit tuning, no post-hoc horizon/quantile selection. This phase only measured whether the signal is real.

Note: neither the earlier `reports/ALPHA_DISCOVERY_2026-09.md` (alpha-discovery) nor this report contains a strategy specification. The output of discovery/validation is evidence, not a trade.

---

## Recommendation (single)

**Do not trade `vol_rel20@1`.**

The single highest-value next step: **extend data** (more history and/or a wider universe) so a genuinely untouched chronological holdout exists, then re-run this exact frozen pipeline once on it. Conditions that would upgrade a future verdict toward A/B/PROMISING:
1. the confirmation test passes on a truly untouched period (not this corpus),
2. temporal positive-window fraction ≥ 0.6,
3. randomization p_two-sided < 0.05 on the untouched period.

Until then the +29.9% remains what it is: a state-dependent discovery-window number, cost-robust but **statistically indistinguishable from chance** and **not reproducible over time**. If a real alpha exists here, it is conditional on high-volatility regimes and must wait to be demonstrated on fresh, never-before-seen data.

---

## Appendix — reproduction

`python -m packages.research.vol_validation --out /tmp/vol_val.json` from the repo root
(resumable; panel cached at `data/historical/alpha_panel.parquet`; reuses
`packages/research/alpha_analysis.py` statistical engines).
All numbers: `reports/volatility_alpha_validation.json`.