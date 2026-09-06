# Alpha Research V2 — Post-Freeze Measurement Report

**Phase:** Alpha Research Engine V2, Phases 1–13 delivered
**Date:** 2026-09-06 · **Pre-registration:** `reports/ALPHA_RESEARCH_V2_PREREG_2026-09.md` (frozen `2026-09-06T13:43:41+05:30`)
**Frozen spec:** `data/alpha_v2/feature_spec.json` (v1, 43 features, 168 hypotheses, families A–H)
**Baseline freeze:** `data/alpha_v2/baseline_freeze.json` (git `773cb52`, holdout_2 locked `11c5eff3…`)
**Machine-readable results:** `reports/alpha_research_v2_results.json`

---

## 1. Corpus and panels

| Universe | Rows | Symbols | Frozen splits |
|---|---|---|---|
| development | 151,542 | 49 | train 2014-01→2023-01 (106,904) · validation 2023-01→2025-07 (30,086) · final-OOS 2025-07→2026-09 (14,552) |
| holdout (frozen, consumed as replication) | 226,118 | 60 | same three splits; pre-2014 rows (split=`''`) excluded as in V1 |

Panels `data/alpha_v2/{development,holdout}_v2_panel.parquet` carry all 43 pre-registered feature columns plus carried `split`, `regime_bucket`, `fwd_ret_{1,3,5,10,20}`, and the V1 exposures (mom/trend/vol/mkt/xs). Built per-symbol (memory-light) from frozen `alpha_panel_*` + raw `d1d` OHLCV; features are causal, labels strictly future.

## 2. Funnel

```
168 pre-registered hypotheses
 ├─ 150 pooled rank-IC hypotheses (A–F, H)           ── scanned on development only
 └─  18 breadth-family market-timing hypotheses (G)  ── date-level, handled separately

development VALIDATION, BH-FDR q ≤ 0.10  ->  48 / 150 candidates   (32%)
  + same-sign replication on dev FINAL-OOS
  + |IC_final| ≥ 0.4 × |IC_validation|    ->  26 / 48 gate survivors (17%)
      └─ scored on the FROZEN holdout (report-only, no selection)
             18 keep the same sign on holdout validation AND final
               └─ most have |holdout IC| ≈ 0.3–0.8× dev |IC| (decay) or wide CIs
```

**Design note (disclosed):** with ~30k–100k matched pairs/symbol, the Fisher-IC test has huge power, so *any* small nonzero IC passes FDR (many q ≈ 1e-6). The binding screens were the magnitude-replication gate and the frozen-holdout audit, which cut the funnel to its real size.

## 3. Family verdicts

| Family | Hypotheses | FDR candidates | Holdout outcome | Verdict |
|---|---|---|---|---|
| A Rel. strength | 30 | 3 (A1·h1, A3·h20, …) | A1 flips sign on holdout final; A3 fades to IC −0.007 (p=0.36) | **FAILED** |
| B Cross-sectional momentum | 25 | 8 | B1/B2 short-horizon fades (|IC|→0, ns on holdout final), B did not survive holdout replication | **FAILED (dev-only)** |
| C Short-term reversal | 15 | 8 | **C3 abnormal 1d-reversal h=1 replicates** (−0.011 p=.035 val, −0.020 p=.008 final); C4/C5 fade | **B. PROMISING (C3@h1)** |
| D Gap/open | 10 | 7 | D3|3 IC replicates (+) but economics negative — see §5 | **C. measurement-inconsistent** |
| E Breakout | 25 | 11 | E1|1 small-|IC| tail, E3|20 flips sign on holdout final, most fade | **FAILED/DECAY** |
| F Volume×price | 15 | 7 | F2|1–5 all fade or flip on holdout | **FAILED** |
| G Breadth/dispersion (timing) | 18 | n/a | see §6 — genuine timing candidates | **B. PROMISING (timing)** |
| H Volatility structure | 30 | 4 | H5/H6|20 cross-window IC +, D3-like cost tension, fails randomization | **C. EXPOSURE PROXY** |

**Headline: 26 of 168 hypotheses cleared the dev gate; 0 are confirmable under the frozen confirmation policy; essentially all short-horizon momentum/reversal-family candidates are dev-period artifacts.**

## 4. Selected deep dives

**C3_rev_abn_mkt1 | h=1 — short-term reversal of daily market-abnormal moves (B. PROMISING)**
- IC: dev-val **−0.0286** (q=0.000) → dev-final **−0.0215** (p=.010) → holdout-val **−0.0110** (p=.035) → holdout-final **−0.0200** (p=.008). Same sign across all four windows.
- Block bootstrap CI [−0.0425, −0.0175]; within-symbol permutation p=0.000; quantile spread −55.7bp, monotone (ρ=−0.90).
- Costs (dev-val, 10% deciles): net **+39.0%** @25bps, +38.3% @50bps; dev-OOS net **+1.8%** — economics decay sharply in the newest window.
- Caveats: holdout long-short mean +14bp/date but only 53% positive dates ⇒ a handful of single-name episodes carry the tail; live magnitude is unstable; ~80% of the IC survives residualization against xs_rel_str20 (incremental, not pure V1 exposure).

**D3_gap_mag_atr | h=3 — gap magnitude scaled by ATR (C. measurement-inconsistent)**
- IC replicates + on dev-val (+0.0324, CI [0.010,0.057]), dev-final, holdout-val (+0.0256 p=.000), holdout-final (+0.0313 p=.000) and randomization p=0.0000.
- Yet non-overlapping-decile economics are **negative** (dev-val −9.8%, dev-OOS −15.3%, holdout −15.9% net). Overlapping-sample IC and non-overlapping rebalanced spread disagree in sign ⇒ the rank signal is not tradeable as specified. Not actionable.

**H5_vol_vs_mkt | h=20 and H6_xs_vol_rank | h=20 — idiosyncratic vol level (C. EXPOSURE PROXY)**
- Cross-window IC replication: dev-val +0.036 → dev-final +0.050 (p=.001) → holdout-val +0.037/+0.033 (p=.000) → holdout-final +0.036/+0.027 (p=.008/.043). Five of five positive.
- Economics: low-turnover monthly deciles, net **+2.1%** dev-val and **+14.5%** dev-OOS @25bps (turnover 0.065).
- **Fails internal bias controls:** within-symbol permutation reports p≈0.96–1.00 (IC fully reproducible by random time-shuffles within symbols) and only 41–51% of symbols are positive (weighted by a few large names). The replicated signal is static cross-sectional vol-return structure, not an incremental time-varying signal — classify as exposure proxy, not an alpha that would survive a speed-bump-style test.

## 5. G-family market timing (18 hypotheses, date-level)

Candidates that replicate from development validation onto the frozen holdout validation:

| Signal | Horizon | dev-val IC (p) | hold-val IC (p) | top−bottom move/fill |
|---|---|---|---|---|
| G1 fraction of risers today | 3d | +0.081 (0.045) | **+0.109 (0.007)** | +0.25% → +0.60% |
| G6 breadth momentum (5d change in G1) | 3d | +0.089 (0.027) | **+0.121 (0.003)** | +0.36% → +0.74% |
| G4 cross-sectional ret dispersion | 1–5d | +0.06–0.09 (ns on val) | **+0.10–0.15 (p≤.01)** | up to +1.15% |

Reverse-caution: G2/G3 (fraction above 20/50-day mean) show **strongly negative** IC on final-OOS in **both** panels (G3|5: −0.318 dev, −0.265 holdout, p≈0) but are flat on train/validation — a 2025-26 regime-top artifact, not a durable signal.

## 6. Robustness and costs

- **Costs (25 bps/side primary; 15/50 sensitivity):** all 26 survivors evaluated. Only C3@h1, H5/H6@h20 (net-positive but exposure-proxy) and G4/G1/G6 timing moves clear a net-cost screen. D3, H3, F2 are cost-negative or sign-inconsistent.
- **Randomization:** 26 survivors × 200 within-symbol permutations — 24/26 are distinguishable from null on dev-val; the 2 exceptions are H5/H6 (exactly the pair with the strongest cross-window IC — the permutation failure is decisive for them).
- **Temporal:** most survivors' IC lives in 2023+ (late regime) or specific bands; C3 is the only survivor whose IC is present in both early (2014–22) and late (2023+) windows.
- **Nonlinear diagnostic (rank vs rank+quadratic, train→validation):** no survivor shows quadratic predictions beating linear OOS (largest delta ≈ 0 on the spear IC scale). Nothing here justifies an ML gate.
- **Symbol/sector/liquidity:** C3 and D3 are broad (per-symbol median |IC|≈0.01–0.02, majority of symbols correct sign); H5/H6 are narrow (weighted by large names).

## 7. Final classifications (A–G scale)

| Grade | Meaning | Survivors |
|---|---|---|
| **A. CONFIRMED** | requires a genuinely untouched corpus (holdout_3+); non-attainable today | — |
| **B. PROMISING** | dev gate + frozen-holdout sign/IC replication + net-positive economics | **C3_rev_abn_mkt1@1** (short-horizon, tail-fragile); **G1@3 / G6@3 / G4@1–5** (market timing) |
| **C. EXPOSURE PROXY / measurement-inconsistent** | replicates cross-window but no incremental time-series alpha (permutation fails) or IC≠economics | **H5@20, H6@20** (vol level); **D3@3, H3@1** (IC vs economics sign clash) |
| **D. DECAY** | dev gate pass, fades to ≈0/ns on the frozen holdout | E1@1/5, E5@1–5, C4@1, C5@1, B1@1/3, A3@20 |
| **X. FAILED** | close to zero or sign-flip across holdout windows | A1@1, B2@1, D2@1, E3@20, E4@3/5, F2@1/3/5 |

Nothing in V2 graduates to a live/paper strategy. Everything beyond these five B-tier rows is dev-period noise.

## 8. Confirmation policy and next steps

Per the frozen spec: **no claim of confirmation without a genuinely untouched corpus.** The 60-symbol frozen holdout is consumed here as replication evidence; `holdout_2` (lock `11c5eff3…`, 130,579 bars) is reserved for V1 transform confirmation and not reused. Upgrading C3@1 / G1@3 / G6@3 / G4@1–5 to **A** requires a holdout_3+ corpus that (i) keeps the same sign with |IC| ≥ 0.4× the dev-val magnitude, (ii) clears 25 bps net, (iii) passes within-symbol permutation.

Recommended if continued: pre-register a **V2-confirmation protocol** against holdout_3+ before acquiring it; fold C3@1 (daily abnormal reversal) into a cost-bounded implementation study only if the tail fragility is accepted; treat G family as a regime-timing overlay worth one more validation cycle.

## 9. Deliverables

- [x] `data/alpha_v2/baseline_freeze.json` (committed `773cb52`) · corpus manifests + splits + immutability note
- [x] `data/alpha_v2/feature_spec.json` + `reports/ALPHA_RESEARCH_V2_PREREG_2026-09.md` (43 features, 168 hypotheses, families A–H, gate, confirmation policy)
- [x] `data/alpha_v2/{development,holdout}_v2_panel.parquet` (60 cols, 49/60 symbols)
- [x] `packages/research/alpha_v2_engine.py` — scan / FDR gate / deep dives (Q1–Q5, CI, bootstrap, permutation nulls, temporal, symbol/sector/liquidity, regime, incremental, nonlinear, costs 15/25/50bps) / G-timing / holdout replication
- [x] `data/alpha_v2/{scan_results,survivor_list,survivor_dossiers,holdout_replication,g_market_timing_*}.json` (full audit trail)
- [x] `reports/alpha_research_v2_results.json` — machine-readable funnel, classifications, A–G verdicts
- [x] `reports/ALPHA_RESEARCH_V2_2026-09.md` — this report