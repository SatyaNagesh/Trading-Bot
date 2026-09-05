# Alpha Discovery — Daily Single-Stock Panel

**Project:** Alpha Discovery Engine · **Data domain:** NSE equities, daily
**Report dates:** 2026-09-05 · **Generated from:** `packages/research/alpha_runner.py`
**Machine-readable results:** `reports/alpha_discovery_results.json` (same content, JSON)

---

## 1. Executive conclusion

**No genuine alpha was demonstrated on this data.**

After screening 105 (feature × horizon) hypotheses with chronological TRAIN /
VALIDATION / FINAL-OOS splits, BH-FDR (q ≤ 0.10) on validation, walk-forward
survival, randomized/block-bootstrap controls and a turnover-cost-aware test:

- **0 features** qualify as **STRONG RESEARCH CANDIDATE** (stable, positive-direction,
  cost-surviving out-of-sample signal).
- **10 volatility-family pairs cluster as PROMISING — MORE DATA** (stable positive sign
  across splits, but weak validation IC, low walk-forward survival, non-monotonic
  quantiles; only one pair survives a cost model on both OOS windows).
- **30 pairs are stable REVERSED SIGNALS**: they predict a *negative* relationship
  (high feature value → lower forward returns). Two of them have hard-statistical
  stability (`trend_sma20_gap@1`, `trend_ema10_gap@1`: negative bootstrap CIs, p<0.01 on
  within-symbol shuffles) — real information in the opposite direction of the naive reading.
- **65 pairs are UNSTABLE** (sign flips across splits), and many train-strong pairs
  (especially market-timing `mkt_ret_5d@horizons`) are curve-fit: large positive
  VALIDATION profits (+44%…+53%) then deeply negative FINAL-OOS (−23%…−25%).

Discipline rule applied: **no strategy is built from any of these** (even flipped).
The strongest item — daily relative-volume `vol_rel20@1` — is a candidate for further
data collection, not a trade.

---

## 2. Dataset & causality

| Item | Value |
|---|---|
| Symbols | 49 NSE equities (SEBI-audited corpus; 48 fixed membership for cross-sectional/market features, HDFCLIFE step-adjustment excluded from universe-wide calculations) |
| Frequency | daily close, Asia/Kolkata timestamps |
| Range | 2014-01-01 → 2026-09-04 |
| Panel rows | 151,184 |
| TRAIN | 106,792 rows (2014 → ~2023) |
| VALIDATION | 30,036 rows |
| FINAL-OOS | 14,356 rows (unused until final scoring) |

Causality: every feature uses prices/data **≤ t**; labels are explicit
`fwd_ret_h = close[t+h]/close[t] − 1` for h ∈ {1, 3, 5, 10, 20} days (data **> t**).
No rolling/leaky statistics enter any feature; trailing quantiles, ATR, BB bands,
realized vol and RSI are all computed on trailing windows only. Panel cached from
`data/historical/alpha_panel.parquet`; `build_index` uses percentage changes
(no cumprod overflow).

---

## 3. Feature library

21 causal features in 6 categories (definitions & rationales in
`packages/research/alpha_features.py` → `FEATURES`; full metadata in the JSON):

- **Trend:** `trend_sma20_gap`, `trend_ema10_gap`, `trend_sma20_slope5`, `trend_strength_20v50`
- **Momentum:** `mom_roc20`, `mom_rsi14`, `mom_macd_hist_norm`
- **Volatility:** `vol_atr_pct`, `vol_realized20`, `vol_pctile_252`, `vol_rel20`, `vol_trend_10v50`, `vol_price_corr20`
- **Price structure:** `struct_breakout20`, `struct_lowdist20`, `struct_bb_z20`, `struct_vwap_gap20`
- **Cross-sectional:** `xs_rel_str20`, `xs_mom_rank20` (per-date rank/z with min-20-symbol guard)
- **Market context:** `mkt_ret_5d`, `mkt_vol_20`

Regime conditioning uses `regime_bucket` = {up, sideways, down} × {low, med, high}
volatility (9 buckets). The legacy RegimeObserver label is near-degenerate and was
not used for conditioning.

---

## 4. Hypotheses & multiple-testing control

- 21 features × 5 horizons = **105 hypotheses**.
- Pre-screen: same sign on TRAIN ∩ VALIDATION with max|IC| ≥ 0.01 → **54 preselected**.
- BH-FDR on VALIDATION p-values (Fisher-z with autocorrelation-adjusted effective N),
  q ≤ 0.10 **and** p < 0.05 → **31 survive**.
- FINAL-OOS scored **once**, as an untouched holdout. Bootstrap/randomized controls run
  on pooled VALIDATION∪FINAL-OOS.
- No "alpha" claim based on p < 0.05 anywhere; the 31 survivors are mostly small-IC
  noise at FINAL-OOS.

---

## 5. IC statistics — headline pairs

Spearman IC per split (TRAIN / VALIDATION / FINAL-OOS), from the FDR survivors:

| feature@horizon | train IC | val IC | final IC | wf surv | decision |
|---|---|---|---|---|---|
| vol_rel20@1 | 0.0053 | 0.0288 | 0.0074 | 0.33 | PROMISING – MORE DATA |
| struct_breakout20@5 | −0.0272 | −0.0230 | −0.0249 | 0.50 | REVERSED SIGNAL |
| struct_bb_z20@3 | −0.0154 | −0.0202 | −0.0158 | 0.58 | REVERSED SIGNAL |
| trend_ema10_gap@1 | −0.0172 | −0.0192 | −0.0167 | 0.75 | REVERSED SIGNAL |
| trend_sma20_gap@1 | −0.0157 | −0.0185 | −0.0139 | 0.67 | REVERSED SIGNAL |
| mkt_ret_5d@5 | −0.0085 | −0.0753 | +0.0153 | 0.58 | UNSTABLE (curve-fit; see §10) |
| struct_breakout20@10 | −0.0320 | −0.0057 | −0.0552 | 0.42 | REVERSED SIGNAL |
| vol_realized20@20 | +0.0616 | +0.0131 | +0.0233 | 0.42 | PROMISING – MORE DATA |

Non-monotonic bucket shapes drive several counter-intuitive rows (negative IC yet positive
cost-aware L/S profit, e.g. `mkt_ret_5d@5`).

Full IC table for all 105 pairs: JSON `ic_table`.

---

## 6. Quantile profiles

For the 31 candidates (5 buckets, per split), FINAL-OOS top-minus-bottom spreads are
economically negligible (mostly −0.02%…+0.13% per horizon) and often **non-monotonic**
(e.g. `trend_sma20_gap@1` final spread +0.025% yet negative IC — a U-shaped bucket
pattern). `single_bucket_dominance` flags were recorded per pair; no pair shows clean
Q1 < … < Q5 monotonicity on train, validation and final OOS simultaneously. This is
the weakest monotonicity evidence in the whole exercise and one reason nothing advances.

---

## 7. Cross-sectional diagnostic (rank L/S)

Per-date top/bottom coverage groups (20/80 default), date-level long-short spread,
bootstrap CI, t-stat, positivity fraction, excess vs equal-weight market. Highlights
(FINAL-OOS, 20/80):

| feature@horizon | LS mean/day | t | dates | CI95 | long>mkt |
|---|---|---|---|---|---|
| vol_rel20@10 | +0.3105% | 2.40 | 283 | (−0.030, 0.680) | + |
| vol_rel20@20 | +0.1608% | 0.82 | 283 | · | · |
| vol_rel20@1 | +0.0623% | 1.50 | 283 | (−0.016, 0.142) | +0.044%/day |
| trend_ema10_gap@1 | +0.1651%‡ | 0.95 | 283 | · | · |
| struct_breakout20@5 | −0.0207% | −0.11 | 283 | · | · |

as long-top/short-bottom. ‡ reverse-direction feature; positive here reflects
non-monotonic bucket shape, not a usable long signal. Almost all other pairs have
|t| < 1 and confidence intervals spanning zero.

---

## 8. Combination & redundancy

3-candidate composites (top by |final IC|: `struct_lowdist20@20`, `mom_macd_hist_norm@20`,
`struct_breakout20@20`) showed high cross-feature correlation and **no additive value**:
single `struct_lowdist20@20` composite IC −0.155 weakens to −0.023 when the three are
averaged in z-space (redundancy dominates). Partial-IC table in JSON. No 2→3→4–5
progression rewarded.

---

## 9. Regime-conditional IC (stability first — no regime strategies)

Conditioning on `regime_bucket` (9 classes) produced **highly unstable** per-regime ICs,
including sign flips between adjacent buckets for the same feature@horizon. Example
`vol_rel20@1` FINAL-OOS: `sideways|high_vol` **−0.142**, `up|med_vol` **+0.076**,
`down|med_vol` **+0.067**, `down|low_vol` **−0.054**. No feature is consistently
positive (or negative) within any regime across splits; per the project's rule, no
regime-contingent alpha claim and no regime strategy is formulated.

---

## 10. Cost-aware long-short

10% long / 10% short rank portfolios (the long-top bucket first), rebalanced every exact
horizon days, cost = turnover × 0.15% per side (0.05% commission + 0.10% slippage).
Benchmark = equal-weight index buy & hold over the same grid. FINAL-OOS:

| pair | gross | net | drag | market_BH | verdict |
|---|---|---|---|---|---|
| vol_rel20@1 | +30.24% | +29.85% | 0.39% | +4.06% | survives costs (but vol_rel20@3 net −0.42%; horizon-fragile) |
| trend_sma20_gap@1 | +3.89% | +3.43% | — | +4.06% | ≈ market; reversed feature |
| struct_breakout20@5 | −19.43% | −19.67% | — | +4.06% | natural direction loses |
| struct_bb_z20@3 | −23.98% | −24.21% | — | +4.06% | natural direction loses |
| mkt_ret_5d@5 | (−) val +52.7% net | **final −23.76%** | — | +4.06% | **curve-fit / regime-dependent** |

The validation-vs-final inversion of the market-timing family (val +44%…+53%,
final −23%…−25%) is the clearest illustration of validation-curve arbitrage in this
corpus.

---

## 11. Bootstrap & randomized controls

Pooled VALIDATION∪FINAL-OOS, 63-day time-block bootstrap (250 sims) + within-symbol
feature shuffles (200 sims):

| pair | obs IC | boot CI95 | p(shuffle) |
|---|---|---|---|
| trend_sma20_gap@1 | −0.0151 | −0.0300…−0.0033 | 0.005 |
| trend_ema10_gap@1 | −0.0165 | −0.0309…−0.0031 | 0.005 |
| trend_sma20_gap@3 | −0.0140 | −0.0419…+0.0083 | 0.010 |
| trend_sma20_gap@5 | −0.0166 | −0.0509…+0.0102 | 0.035 |

These are the only hard-statistically-confirmed signals, and both are **negative**
(reversed) relationships at the 1-day horizon.

---

## 12. Walk-forward survival

12 chronological discovery blocks across TRAIN→VALIDATION; survival = same sign,
max|IC| ≥ 0.005, and at least one-side p < 0.1. Top survivors:

| pair | survival | blocks |
|---|---|---|
| trend_ema10_gap@1 | 0.75 | 9/12 |
| xs_rel_str20@1 | 0.75 | 9/12 |
| struct_vwap_gap20@1 | 0.67 | 8/12 |
| trend_ema10_gap@3 | 0.67 | 8/12 |
| trend_sma20_gap@1 | 0.67 | 8/12 |

High survival is a *stability* metric and is not treated as positive-direction
evidence — every top survivor is a negative-direction (reversed) or weak feature.

---

## 13. Final ranking & decisions

105 rows in JSON (`ranking`). Aggregate:

- **STRONG RESEARCH CANDIDATE: 0**
- **COST-FRAGILE: 0**
- **PROMISING – MORE DATA: 10** — all volatility class:
  `vol_rel20@1`, `vol_atr_pct@1/3/5`, `vol_realized20@1/3/5/10/20`, `mkt_vol_20@1`.
  Rationale: stable positive sign across splits but low/irregular walk-forward
  survival (0.00–0.42), tiny validation ICs, non-monotonic quantiles, and (where
  cost-tested) horizon-dependent net results. Only `vol_rel20@1` survives costs on
  both OOS windows.
- **REVERSED SIGNAL: 30** — stably-negative pairs, mostly short-horizon trend /
  structure / relative-strength (gap-to-SMA/EMA, breakout, BB-z, VWAP-gap,
  xs_rel_str20). Natural long-top/short-bottom loses.
- **UNSTABLE: 65** — sign flips across splits.

---

## 14. Failed hypotheses & what it taught us

- 105 screened → 54 preselected → 31 FDR survivors → **0 actionable**.
- Train/validation "alpha" in market timing (`mkt_ret_5d`) is pure validation-curve
  arbitrage; it inverted sign and went deeply negative the moment it was truly OOS.
- Momentum at 1–5d is not predictive out of sample; MACD-histogram "wins" are within
  FDR noise (±0.02–0.13% bucket spreads).
- Relative-volume at the daily horizon is the only cost-surviving positive lead, and
  even it is horizon-fragile (`vol_rel20@3` net ≤ 0) and regime-unstable.
- Two features (`trend_sma20_gap@1`, `trend_ema10_gap@1`) carry genuine, reproducible
  information — but in the *reverse* direction.

---

## 15. Recommended next steps

1. **Extend universe/period for the vol family** — test `vol_rel20` at 1–10d on a
   broader or longer corpus before anything is promoted; its validation IC (+0.029)
   and final (+0.007) are far apart.
2. **Re-examine reversed signals with an explicit inversion discipline** (falsifiable:
   SHORT high gap-to-EMA, LONG low). Requires a pre-registered strategy spec, HARD
   (no repurposing post-hoc); per project policy this is out of scope for discovery.
3. **Decompose vol_rel20 by regime** once more data exists (currently unstable across
   `regime_bucket`, incl. a −0.14 IC in `sideways|high_vol`).
4. HARD RULE respected: **no strategy is derived from this report's one-off findings.**

---

## 16. Appendix — reproduction

- `python -m packages.research.alpha_runner --out /tmp/alpha_full.json`
  (resumable: saves after every phase; caches `data/historical/alpha_panel.parquet`)
- Analysis functions: `packages/research/alpha_analysis.py`
  (IC w/ autocorr-adjusted effective N, BH-FDR, quantiles, L/S, block bootstrap,
  within-symbol shuffle, partial IC, composite z, cost-aware L/S)
- Panel/labels: `packages/research/alpha_dataset.py`
- Feature definitions: `packages/research/alpha_features.py` → `FEATURES`
- Full numbers: `reports/alpha_discovery_results.json`