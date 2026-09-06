# vol_trend_10v50 → Alpha? — Final Investigation Report

**Feature:** `vol_trend_10v50 = SMA(volume, 10) / SMA(volume, 50) − 1`
**Date:** 2026-09-06 · **Status:** FINAL
**Classification:** **C. EXPOSURE PROXY** (secondary: B. PREDICTIVE BUT NOT MONETIZABLE)

> This report closes the 14-phase investigation into why `vol_trend_10v50` shows a
> *replicated* positive predictive IC but a ~zero *tradable* cross-sectional spread.
> No pipeline or frozen holdout was modified. Any monetization transform was treated
> as a NEW hypothesis and pre-registered on development/validation **before** exactly
> one evaluation on the untouched **holdout_2** universe.
>
> **Bottom line:** the replicated IC is essentially fully explained by cross-sectional
> exposures (volatility level, ATR, momentum, trend, beta, size, liquidity); the
> independent-holdout residual IC is ≈ 0.003 and every pre-registered monetization
> transform fails the development-validation gate (net-of-25bps CI upper bound ≤ 0).
> **The signal is an exposure proxy and is NOT monetizable at any pre-specified construction.**

---

## 1. Classification within A–G

| Criterion (A requires all) | Evidence | Pass? |
|---|---|---|
| Replicated relationship | IC sign replicates across dev/holdout/holdout_2 observationally in 2023+ | ✔ (but exposure-explained) |
| Meaningful effect | Raw IC 0.015–0.058; **residual IC ≈ 0.003 after exposures** | ✘ |
| Tradable spread | Gross LS ≈ 0 ± 5 bps/day; all net25 < 0 | ✘ |
| Sufficient observations | 17.5k (holdout) / 14.5k (dev) final-OOS rows | ✔ |
| Realistic costs at net | −0.05 … −0.19 %/day net25 everywhere | ✘ |
| Stable across regime/period | Sign concentrates 2023+; regime signature flips dev vs holdout | ✘ |
| No concentration problem | HHI ≈ 0.02–0.03, top-5 ≈ 0.18–0.22 | ✔ (mild) |
| No leakage | Pre-registered (commit `f6e3adc`); single holdout_2 confirmation | ✔ |
| Robust construction | Winsor/drop IC movement ≤ 0.002 | ✔ |

**Final: C. EXPOSURE PROXY** — the predictive content of `vol_trend_10v50` is inherited
from its correlations with established, non-rebating cross-sectional attributes
(vol level ρ≈0.31–0.41, ATR ρ≈0.41, trend ρ≈0.14, momentum ρ≈0.10; size/liq ≈ −0.01),
NOT from volume-trend information proper. Because a volume-trend *level* is simply a
standardized volatility-level factor, its IC is not independent signal.
Secondary classification **B** (predictive but not monetizable) is also satisfied and is
of record in the prior phase; the exposure attribution now resolves the mechanism.
Explicitly NOT: A (fails spread/costs/effect), D (dev regime signature
`down|med_vol +0.221` is not reproduced on holdout, where the top regime is
`up|high_vol +0.143`), E (IC *sign* replicates — not instability), F (definition is
deterministic and correctly implemented), G (evidence is conclusive).

---

## 2. Definition

- **Formula:** `vol_trend_10v50_t = SMA(V_t, 10)/SMA(V_t, 50) − 1`, daily, on raw traded
  volume from a deterministic re-acquisition of the frozen universes.
- **Horizons:** fwd daily (`h1`) and 3-day (`h3`) next-close returns, rank-adjusted
  Spearman IC within date.
- **Universes / splits (frozen):**
  - *Development*: 49 symbols; TRAIN 2014-01→2023-01, VALIDATION 2023-01→2025-07,
    FINAL-OOS 2025-07→2026-09 (296 final-OOS days).
  - *Frozen holdout*: 60 symbols, identical split dates (292 final-OOS days).
  - *holdout_2*: 39 symbols (top-40 by marketCap snapshot minus ASTRAL.NS failed),
    disjoint from the other two; dataset lock `11c5eff3…`; bars_total 130,579.

## 3. Why the IC is positive

The high-decile of `vol_trend_10v50` is a *volatility-spike* tilt:

- **Correlations of the signal (final-OOS):** `vol_atr_pct 0.412`, `vol_pctile_252
  0.404`, `vol_realized20 0.358`, `mkt_vol_20 0.228`, `vol_rel20 0.207` (dev);
  0.363/0.357/0.29 on holdout. Cross-price momentum/trend are ≈ 0.05–0.14.
- During 2023–2026 high-vol names mean-reverted upward (esp. in holdout, top regime
  `up|high_vol`), turning the vol-level tilt into a short-window IC win.
- Removing exactly these exposures (within-date, spline-residualized, full-history
  lookbacks) **destroys the IC**: holdout final-OOS residual `0.0152→0.0026` (h1),
  `0.0275→0.0034` (h3), residual p-value 0.73 / 0.65. On dev, validation residual
  `0.0180→0.0035`; final-OOS residual `0.0581→0.0211` (an outlier-laden short window).
  → The "edge" is the vol-level premium, visible only through the vol-trend lens.

## 4. Distribution

| Statistic (final_OOS pooled) | Development | Frozen holdout |
|---|---|---|
| p1 / p5 / p50 / p95 / p99 | −0.51 / −0.40 / **−0.05** / 0.52 / 0.86 | −0.62 / −0.46 / **−0.07** / 0.69 / 1.24 |
| Avg daily std (within date) | 0.251 | 0.345 |
| Days with < 20 unique obs | 0 | 0 |
| Share of days median = 0 | 0.0 | 0.0 |

Real, well-spread, right-skewed; median ≈ −5…−7% (volume ratios cluster below 1),
dispersion large enough that the IC isn't an artifact of pathological constants.

## 5. Quantile behavior (forward returns by signal decile)

| Decile fwd mean % (final_OOS) | 0 (low) | 1 | 2 | 3 | 4 (high) | Q5−Q1 | Shape |
|---|---|---|---|---|---|---|---|
| dev h1 | −0.061 | −0.029 | +0.020 | +0.077 | +0.078 | **+0.138** | monotonic_up |
| dev h3 | −0.155 | −0.063 | +0.037 | +0.185 | +0.255 | **+0.411** | monotonic_up |
| holdout h1 | +0.012 | −0.013 | +0.004 | +0.035 | +0.102 | +0.089 | u_shaped |
| holdout h3 | +0.032 | −0.030 | +0.003 | +0.114 | +0.307 | +0.275 | u_shaped |

The dev panel shows an attractive monotonic ramp; the frozen holdout shows a *u-shape*
(long tail marginal). The shape itself is not replication-stable, and the spread does
not survive costs (section 9—10).

## 6. Cross-sectional spread (long-short)

- dev final-OOS: **LS mean +0.0055%/day** (t = 0.10), long leg +0.013, short +0.008,
  positive-date fraction 0.48 — indistinguishable from zero.
- holdout final-OOS: **LS mean −0.0148%/day** (t = −0.21), long +0.042, short +0.057.
- Relative (within-date, size/time/price-scaled) LS ≈ 0 on all panels. → the reported
  "decile spread" of +0.4 bp/day in prior phases is a level artifact, not a spread.

## 7. Symbol / sector concentration

- Dev final-OOS: 49 syms, 73.5% positive per-symbol IC, median IC 0.040/0.065,
  **HHI(abs IC share) 0.029**, top-5 share 0.224. Top symbols EICHERMOT +0.161,
  ONGC +0.125, WIPRO −0.116 (opposite sign), … — **no single name drives it**.
- Holdout final-OOS: 60 syms, 56.7%/61.7% positive, median 0.022/0.045, HHI 0.023,
  top-5 0.186. Sector leaders differ every split (Automobile/Construction on dev;
  Logistics/Metals on holdout) → no stable sector story.

## 8. Market-vs-relative exposure

- Market timing (daily IC vs market state): dev ρ=0.109 (p 0.061), holdout ρ=0.022
  (p 0.704) → no reliable market-beta.
- Relative IC (pooled, exposures-removed vs market): dev +0.0168 (p 0.042),
  holdout **+0.0046 (p 0.543)** → the *relative* signal is only significant on dev,
  i.e. it does not survive out-of-universe.
- The positive raw IC largely reflects co-movement with high-vol/rising names, not
  idiosyncratic volume-trend skill.

## 9. Pre-specified monetization tests (P8, pre-registered at commit `f6e3adc`)

Five transforms frozen in `data/holdout_2/transform_spec.json`; **costs 25 bps/side**
(15 bps sensitivity); **gate = dev-VALIDATION** net25 mean > 0 ∧ block-bootstrap
(block=63, n=1000, seed 7) CI lower > 0, then BH-FDR q ≤ 0.10.

| Transform | dev val net25%/day | dev val CI95 | Gate |
|---|---|---|---|
| T1 decile_raw | −0.1010 | [−0.211, −0.006] | ✘ |
| T2 quintile_raw | −0.0708 | [−0.141, −0.015] | ✘ |
| T3 decile_volstd | −0.1034 | [−0.201, +0.007] | ✘ |
| T4 decile_sector_relative | −0.0613 | [−0.100, −0.039] | ✘ |
| T5 decile_neutralized | −0.0840 | [−0.180, −0.014] | ✘ |

**Gate selected `[]`** — no transform advanced, so **no holdout_2 confirmation run was
valid or performed** (confirmation is conditional on a gate pass by design).

## 10. Costs / slippage

- Turnover 0.10–0.21/day per leg across T1–T5 → single-sided daily cost at 25 bps =
  0.05–0.10%/day just to trade. Of the 45 transform-split runs, **42 had negative net25**
  (range −0.03 … −0.19%/day, Sharpe −0.5 … −2.9). The only 3 positive net25 runs were
  **all in the untouched holdout_2 panel** (T1 val +0.0006, T3 val +0.0632, T3 final
  +0.103) — i.e. they appeared exactly where, by design, no gate selection was allowed.
- At the 15 bps sensitivity level dev net is still negative everywhere (−0.03 … −0.09%/day).
- Those 3 holdout_2 positives were **not pre-selected**, their CIs include 0
  (T3 val [−0.111,+0.138]; T3 final [−0.107,+1.527]), and with 30 unselected
  per-panel runs such observations are expected noise. They are reported for
  transparency and are **not** claimed as evidence.

## 11. Regime behavior

- Dev final-OOS h3 top regimes: `down|med_vol +0.221`, `down|low_vol +0.127`,
  `up|high_vol +0.041` — IC strongest in *down* regimes.
- Holdout final-OOS h3 top regimes: **`up|high_vol +0.143`**, `sideways|high_vol +0.096`,
  and `down|low_vol −0.068` (bottom tier) — the signature *flips* universe-to-universe.
- → No reproducible regime rule; the positive IC is best described as "high-vol at any
  market tone during 2023–2026", i.e. again a vol-level exposure, not a regime-timing edge.

## 12. Temporal stability

| Band | dev h1 frac_pos / med IC | dev h3 | holdout h1 | holdout h3 |
|---|---|---|---|---|
| TRAIN 2014–2023 (35 qtrs) | 0.43 / −0.0057 | 0.46 / −0.0022 | 0.43 / −0.0078 | 0.49 / −0.0043 |
| OOS 2023–2026 (15 qtrs) | 0.67 / +0.0217 | 0.67 / +0.0253 | 0.67 / +0.0050 | 0.60 / +0.0058 |

- Non-positive (≈ −0.006) for nine years; positivity is a 2023+ phenomenon.
- In the OOS era the IC is present in *both* universes but the **holdout is ~4× weaker**
  (median 0.005 vs 0.022) — exactly the shrinkage expected from an exposure proxy whose
  premium weakened out-of-universe. Best window in both: 2026-01 (dev +0.117, ho +0.105).

## 13. Outlier robustness

| final_OOS | base IC | 1–99 winsor | drop 0.5% ext | max Δ |
|---|---|---|---|---|
| dev h3 | 0.0581 | 0.0581 | 0.0573 | 0.0008 |
| holdout h3 | 0.0275 | 0.0275 | 0.0279 | 0.0004 |

IC is robust to extreme observations — but a signal can be both robust *and* exposure-driven;
robustness does not rescue monetizability.

## 14. Holdout-contamination status

- **Clean.** The frozen holdout was consumed only by the original signal test; every
  monetization transform was pre-registered (commit `f6e3adc`) against dev/validation
  BEFORE any touching of holdout_2. holdout_2 was acquired afterwards under lock
  (`11c5eff3c3f3…`, manifest checksums verified, 39/39 eligible), and only the
  conditional confirmation — which never triggered — was permitted on it.
- holdout_2 result rows (45 transform-split runs, observable and reported here) are
  reported for transparency and are consistent with the "no edge" conclusion.

## 15. Decision

**C. EXPOSURE PROXY** (secondary **B. PREDICTIVE BUT NOT MONETIZABLE**).

`vol_trend_10v50` ≠ alpha. Its replicated, significant, robust IC is a vol-level factor
wearing a volume-ratio costume:

1. raw IC **is** significant (HO @3 +0.0275, p 2.9e-4; rand p 0.00) but flips to
   ≈ 0.003 after exposure removal (p 0.65) — the independent information is ~zero;
2. the decile spread is 0 (dev LS t=0.10; holdout LS −0.21) and every net-of-cost run is
   negative after the pre-registered 25 bps;
3. no transform passed the dev gate, hence holdout_2 was never officially confirmation-run;
4. the only place the IC looks tradable (dev final-OOS) is a regime/period corner that does
   not reproduce in the frozen holdout or in holdout_2.

**No strategy is warranted, and none is created.** This closes the investigation with a
negative, pre-registered, auditable conclusion.

---

## Reproducibility

| Artifact | Location |
|---|---|
| Pre-registration (freeze) | `reports/VOL_TREND_SIGNAL_TO_ALPHA_PRE_REGISTRATION_2026-09.md` |
| Transform spec (frozen) | `data/holdout_2/transform_spec.json` |
| Diagnostics engine | `packages/research/vt_signal.py` |
| Transform evaluator | `packages/research/vt_transforms.py` |
| Diagnostics JSON | `reports/vt_signal_diagnostics.json` |
| Transform results JSON | `reports/vt_transforms_results.json` |
| Verdict (machine-readable) | `reports/vol_trend_signal_to_alpha.json` |
| holdout_2 lock / manifest | `data/holdout_2/dataset_lock.json`, `manifest.json` |

Evidence record for the raw-IC significance (frozen, prior-phase source of truth):
`reports/INDEPENDENT_HOLDOUT_VALIDATION_2026-09.md` — `vol_trend_10v50@3` dev-val
+0.0201 (0.009), dev-final +0.0539 (1.3e-10), HO-val +0.0159 (0.037), HO-final +0.0275
(2.9e-4), HO LS20/80 +0.015% (t 0.14), rand p 0.00, boot IC CI [−0.016, +0.059].