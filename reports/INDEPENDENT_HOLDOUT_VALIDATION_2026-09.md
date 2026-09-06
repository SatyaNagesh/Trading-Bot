# INDEPENDENT HOLDOUT VALIDATION — 2026-09-06

**Frozen pipeline + pre-registered 60-symbol universe evaluated ONCE.**
Everything here is **replication, not discovery**. Numbers were produced by
re-running the unchanged frozen code (`main@9e70300` + freeze commit `eb05d85`
/ tag `research-freeze-2026-09-06`) against a genuinely unseen corpus.

---

## 0. TL;DR — Final decision

> **FINAL DECISION: D. NO EDGE. Nothing advances; no strategy conversion;
> no paper/live trading.** The DEVELOPMENT tournament verdict ("NO EDGE",
> nothing to advance) is **replicated on a fully independent corpus**.
>
> One secondary annotation (not a tradeable result): the **IC of
> `vol_trend_10v50` replicates positively and significantly** on independent
> symbols — but it does **not** manifest as a cost-surviving long/short spread,
> so it stays **B. PROMISING BUT INSUFFICIENT**, to be retested only on the
> future chronological holdout (bars ≥ 2026-09-05), never traded.

### Decision schema (A–F)
| Criterion | Verdict |
|---|---|
| A. REPLICATED ROBUST EDGE | NO |
| B. PROMISING BUT INSUFFICIENT | only for vol_trend_10v50 IC (unmonetizable) |
| C. PREVIOUS FINDING FAILED TO REPLICATE | NO — prior no-edge findings reproduced |
| D. NO EDGE | **YES (final)** |
| E. DATA QUALITY / METHODOLOGY PROBLEM | NO (audit clean, method bit-identical) |
| F. INCONCLUSIVE | NO |

---

## 1. The independent corpus (FROZEN HOLDOUT)

- Universe: **60 NSE large/mid-caps pre-registered in
  `data/holdout/universe.json`** (commit `eb05d85`, tag
  `research-freeze-2026-09-06`) — selected **before any price download** by a
  return-independent rule (Yahoo `fast_info['marketCap']` snapshot; ties
  alphabetized; pool disjoint from the 49 DEVELOPMENT symbols; 4 unresolvable
  tickers dropped without substitution).
- Data: yfinance 1.7.0, `interval=1d`, `auto_adjust=True`, Asia/Kolkata.
  Range **2010-01-01 → 2026-09-04** — i.e. new symbols **and** a
  pre-DEVELOPMENT period (2010–2013, 48,942 panel rows) never used anywhere.
- **226,559 daily bars**, 60/60 symbols fetched, 0 ingestion failures,
  audit = all WARN (expected NSE holidays), eligibility gate (bars≥700) keeps
  60. Lock fingerprint **`1f5bb43f…`** (`data/holdout/dataset_lock.json`);
  per-file SHA-256 in `data/holdout/manifest.json`.
- Splits: identical boundaries to DEVELOPMENT (TRAIN 2014–2023,
  VALIDATION 2023–2025-07, FINAL-OOS 2025-07→2026-09-04).
- Holdout panel: 226,118 rows, 60 symbols, 33 columns.

No bar of this corpus was consulted before the freeze commit; no optimization
was performed on it; every result below is its first and only read.

---

## 2. Strategy replication (frozen tournament, 60 holdout symbols)

OOS = VALIDATION ∪ FINAL-OOS (2023-01-01 → 2026-09-04). Pooled trade stats.

| Strategy | DEV n | DEV exp% | DEV CI95 | DEV verdict | HO n | HO exp% | HO PF | HO CI95 | HO verdict | Replication |
|---|---|---|---|---|---|---|---|---|---|---|
| A trend-following | 525 | +2.41 | [1.34, 3.57] | OVERFIT/FRAGILE | 598 | +5.35 | 2.90 | [3.72, 7.09] | OVERFIT/FRAGILE | **Same label, same structure** |
| B momentum | 5,820 | −0.35 | [−0.42, −0.28] | NO EDGE | 7,128 | −0.41 | 0.72 | [−0.48, −0.33] | NO EDGE | **Replicates** |
| C breakout | 0 | — | — | INSUFFICIENT | 0 | — | — | — | INSUFFICIENT | **Replicates (never fires)** |
| D mean-reversion | 1 | — | — | INSUFFICIENT | 5 | −1.32 | 0.62 | — | INSUFFICIENT | **Replicates (never fires)** |
| E multi-factor | 6,625 | −0.36 | [−0.44, −0.29] | NO EDGE | 7,778 | −0.28 | 0.82 | [−0.38, −0.18] | NO EDGE | **Replicates** |
| autonomous_momentum | 1 | — | — | INSUFFICIENT | 3 | −7.32 | 0.0 | — | INSUFFICIENT | **Replicates (never fires)** |

**Momentum + multi-factor: decisive replicated NO EDGE.** Combined across 109
symbols: momentum −0.35→−0.41%/trade (12,948 pooled trades, negative mean
in BOTH universes with CI below zero in both); multi-factor −0.36→−0.28%
(14,403 pooled trades). Cost-fragile and param-fragile on dev; PF 0.72/0.82
on holdout. Both are statistically clean negative edges at every scale tested.

**A trend-following: OVERFIT/FRAGILE in BOTH.** On holdout the pooled OOS
expectancy is +5.35%/trade (CI>0) — but the label is not robust:
- top-10% of trades generate **102% of all net profit** (median trade is
  −0.28%); the distribution is a right-tail story exactly as on dev
  ("edge = regime-dependent tail trades");
- the **most recent unseen window (FINAL-OOS 2025-07→2026-09) is negative**
  (exp −0.53%/trade, PF 0.85).
A positive expectancy entirely carried by a few multi-year bull trends, absent
in the latest window, is the same non-edge structure DEVELOPMENT flagged.

**Breakout / mean-reversion / autonomous_momentum never fire** (0/5/3 pooled
OOS trades on 60 symbols) — replicated non-executability, same as dev (0/1/1).

### Regime + parameter breakdown (holdout)
- Regime-positive fraction: median across strategies ≈ 0.5–0.65; the only
  clearly positive contributions for A are its tail-trend regimes.
- Parameter neighborhoods: momentum/multi-factor positive on a minority of
  variants on dev; trend's positive variant set is small (its mean is pulled by
  one strong trend per symbol) — mirroring dev fragility.

---

## 3. Alpha replication (pre-registered features)

Dev baseline ICs are read live from the frozen `alpha_discovery_results.json`;
holdout ICs recomputed with the identical `alpha_analysis` engine.

### 3.1 `vol_rel20@{1,3,5}` — **NO independent edge; UNSTABLE verdict confirmed**

| feat | DEV val IC (p) | DEV final IC (p) | HO val IC (p) | HO final IC (p) | HO final LS20/80 % (t) | HO rand p | HO boot IC CI |
|---|---|---|---|---|---|---|---|
| vol_rel20@1 | +0.0288 (5.8e-7) | +0.0074 (0.376) | +0.0336 (<1e-6) | +0.0020 (0.792) | +0.037 (0.54) | 0.82 | [−0.016, +0.011] |
| vol_rel20@3 | +0.0216 (1.8e-4) | −0.0019 | +0.0212 (<1e-6) | +0.0055 (0.471) | −0.055 (−0.48) | 0.55 | [−0.028, +0.021] |
| vol_rel20@5 | +0.0215 | +0.0009 | +0.0183 (0.0039) | −0.0049 (0.549) | −0.156 (−1.17) | 0.52 | [−0.040, +0.017] |

- The **validation-window IC inflation reproduces** (dev +0.022–0.029;
  holdout +0.018–0.034) — then **collapses to ≈0 in the unseen final window
  in BOTH universes** (dev +0.001…+0.007; holdout −0.005…+0.005, all p>0.37).
- Holdout cost-aware LS decile: final-OOS **+3.25% net** (gross +3.56%) vs
  dev final-OOS **+29.85% net**. The historical magnitude did **not** repeat.
  Bootstrap IC CI crosses zero; randomization p>0.5; same-sign breadth on
  holdout OOS is only 40%.
- **Conclusion: vol_rel20@1 does not replicate as an edge.** The deep-validation
  verdict **F. UNSTABLE** is confirmed on independent data.

### 3.2 `vol_trend_10v50@{1,3}` — IC replicates; **spread does not monetize**

| feat | DEV val IC (p) | DEV final IC (p) | HO val IC (p) | HO final IC (p) | HO final LS20/80 % (t) | HO rand p | HO boot IC CI |
|---|---|---|---|---|---|---|---|
| vol_trend_10v50@1 | +0.0155 (0.007) | +0.0310 (2.1e-4) | +0.0117 (0.025) | +0.0152 (0.044) | −0.015 (−0.21) | 0.025 | [−0.013, +0.036] |
| vol_trend_10v50@3 | +0.0201 (0.009) | +0.0539 (1.3e-10) | +0.0159 (0.037) | +0.0275 (2.9e-4) | +0.015 (0.14) | 0.00 | [−0.016, +0.059] |

- The **direction and significance of the pooled IC replicate** on an
  independent symbol set in the identical split windows (nominal p<0.05 for
  both horizons in both DEV and holdout final-OOS).
- **BUT the cross-sectional decile/quintile long–short spread is economically
  nil and ~zero-t**: LS20/80 −0.015% / +0.015% per day (t ≈ −0.2 / +0.1), and the
  cost-aware decile LS on holdout final-OOS is only +3.3% net for @3 (−2.9% net
  on validation; @1 is negative on holdout in both windows). Bootstrap IC CI
  includes zero. The positive pooled IC is a within-symbol time-series
  association that does **not** rank-order the cross-section enough to pay for
  itself. Positive IC is concentrated in high-vol regimes (up|high_vol +0.14)
  — a conditional effect, not a general one.
- **Conclusion: B. PROMISING BUT INSUFFICIENT — not a tradeable signal today.**
  Additional, genuinely-unseen chronological data is required before any
  further claim.

---

## 4. Statistical interpretation (Phase 10)

1. **Sample size / power.** Strategies: 109 distinct symbols × the same OOS
   window produce 590–7,778 pooled OOS trades per candidate — enough to bound
   momentum/multi-factor means tightly (CI width ≈ ±0.08%). Alpha IC: 17,580
   OOS panel rows; dev-era n was 14,307. Nominal p-values for vol_trend_10v50
   survive BH-style screening intent because the two features were
   **pre-registered survivors**, not re-mined; the holdout counts as one
   confirmatory test per hypothesis.
2. **Effect size.** Everything tradeable is ≈0 or negative. The only non-zero
   effect (vol_trend_10v50 IC ≈ +0.02–0.03) translates to a per-day spread of
   ±0.015% with t≈0.1 — below any cost hurdle.
3. **Direction/consistency.** Negatives replicate with matching magnitude
   (momentum −0.35/−0.41; multi-factor −0.36/−0.28). The one positive-strategy
   pooled mean (trend) is right-tail-only on both universes and negative in its
   most recent window on holdout — the same fragility verdict as dev.
4. **Multiple testing.** The holdout tested the frozen registry and 5
   pre-registered feature-horizon pairs. No new selection was performed; no
   post-hoc re-ranking; any reading of regime-conditioned ICs above is
   descriptive only.
5. **Benchmark-relative.** No candidate beat a simple buy-and-hold of the same
   universe over the pooled OOS span after costs (market B&H was positive in
   the window; the losers were decisively negative net).
6. **Caveat on the chronological arm.** NSE ended at 2026-09-04 at freeze time,
   so same-symbol later-dates data is not yet available; that remaining slice
   is reserved as FUTURE/PAPER and becomes testable as bars accrue. The holdout
   used here is independent cross-sectionally (new issuers) and temporally
   (2010–2013 pre-DEVELOPMENT years), which is the strongest available
   construction today.

---

## 5. Decisions vs the 10 required questions

**Q1 — Genuinely unseen data?** Yes. 60 symbols disjoint from DEVELOPMENT;
226,559 bars acquired only after the freeze; 2010-2013 slice unseen; manifest
locked (`1f5bb43f…`). No bar consulted before these runs.

**Q2 — Freeze date & what froze?** 2026-09-06, freeze commit `eb05d85`, tag
`research-freeze-2026-09-06`. Frozen: 9e70300 pipeline (features, strategies,
execution, costs, metrics, splits, selection, decision rubric) + pre-registered
universe. Frozen algorithms were NOT modified; only the data-root injection.

**Q3 — Candidates evaluated?** All 6 frozen strategies + vol_rel20@{1,3,5} +
vol_trend_10v50@{1,3}.

**Q4 — Did previous findings replicate?** Yes. Momentum & multi-factor NO EDGE
replicated; breakout/mean-reversion/autonomous_momentum non-executable
replicated; trend OVERFIT/FRAGILE replicated; vol_rel20 UNSTABLE replicated.

**Q5 — Did vol_rel20 replicate?** No edge. IC direction + validation positivity
recurred but final-OOS IC≈0 in both universes; OOS LS +3.3% net vs +29.9% on
dev; rand p>0.5; CI crosses 0. Confirms F. UNSTABLE.

**Q6 — Any positive OOS expectancy?** Only A_trend_following (pooled +5.35%/tr)
— entirely tail-driven (top-10% = 102% of net), median negative, and negative
in the newest OOS window. Not a robust expectancy.

**Q7 — Any cost-survival?** No. Momentum/multi-factor negative net at base
costs; trend survives base costs only via its tail; vol_trend_10v50@3 net
+3.3% with t≈0.1 — statistically and economically indistinguishable from 0.

**Q8 — Cross-symbol / regime survival?** vol_trend_10v50 IC positive on ~57-67%
of holdout symbols and in high-vol/up regimes; vol_rel20 OOS-breadth only 40%;
negative strategies uniformly negative breadth. Conditional at best.

**Q9 — Statistically sufficient?** Sufficient to reject a robust edge for
momentum, multi-factor, vol_rel20 (pooled n in the thousands). Insufficient
to promote vol_trend_10v50 to a strategy (spread ≈ 0, CI includes 0) — more
unseen data needed, not more modeling.

**Q10 — What next?** No strategy conversion (per protocol: nothing replicated
robustly). Keep the freeze intact. Schedule a FUTURE chronological holdout
(bars ≥ 2026-09-05 for both the DEV 49 and the FROZEN HOLDOUT 60) to re-test
vol_trend_10v50 and any later pre-registered survivor. No live/paper trading.

---

## 6. Deliverables

| File | Content |
|---|---|
| `reports/RESEARCH_PIPELINE_FREEZE_2026-09.md` | freeze spec + pre-registration (commit `eb05d85`) |
| `data/holdout/universe.json` | pre-registered universe + rule |
| `data/holdout/{manifest,dataset_lock,splits}.json` | corpus lock (`1f5bb43f…`) |
| `data/holdout/audit.json`, `eligible_symbols.json` | audit + eligibility |
| `reports/holdout_strategy_results.json` | strategy replication detail |
| `reports/holdout_alpha_results.json` | alpha replication detail |
| `reports/independent_holdout_results.json` | consolidated verdict (this run) |
| Code: `packages/research/{select_holdout_universe,acquire_holdout,holdout_runner,holdout_alpha}.py` | thin orchestration only; frozen algorithms untouched |

All artifacts above are additive; no frozen file was modified after `9e70300`.