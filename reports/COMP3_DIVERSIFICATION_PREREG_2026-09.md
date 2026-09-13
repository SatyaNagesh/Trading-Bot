# COMP3 Diversification Research — Pre-Registration (Phases 1-3)

**Date:** 2026-09-13
**Status:** Pre-registered BEFORE any development analysis, cap selection, or
new-data acquisition in this experiment. Committed before Phase 4 runs.

---

## Phase 1 — Freeze COMP3_STRATEGY_V1 as immutable baseline

- **Git commit of final holdout-4 state:** `c5eb215` (main)
- **Holdout-4 corpus lock:** `8154a050868f15e4f336520c3e2c49c89f0a781412cb9c0a1b2ad43bff673e11`
- **Strategy spec:** `reports/COMP3_STRATEGY_SPEC_2026-09.md` + `reports/COMP3_STRATEGY_FREEZE_2026-09.md`
- **Holdout-4 result:** `reports/COMP3_HOLDOUT4_CONFIRMATION_2026-09.md` →
  **E CONCENTRATION-FRAGILE / NOT CONFIRMED** — no paper trading.

V1 rules are NOT modified and are used only as a benchmark.

### V1 constructions (reconstructed on DEVELOPMENT for comparison)
- `V1_DECILE_EQ` — frozen COMP3 score, top/bottom **4** names/side, equal weight 1/4.
- `V1_QUINTILE_EQ` (= D2) — top/bottom **8** names/side, equal weight 1/8.
  (m=4 and m=8 match the decile/quintile definitions of the 40-symbol holdout
  universes; the same m is used on every corpus for comparability.)

## Phase 2 — D1: one simple weight-cap rule

**D1** = frozen COMP3 ranking/selection, equal-weight positions, strict maximum
per-symbol gross weight.

Mechanism: on each active date take the top-`m_C` and bottom-`m_C` ranked names,
each side equal weight `1/m_C`. Then `max |w| = 1/m_C ≤ C` with
`m_C = ceil(1/C)` per side and feasibility `2·m_C ≤ N_universe`.

- Candidate caps (pre-registered, determined by feasibility on a 40-symbol
  universe): `C ∈ {5%, 6%, 8%, 10%, 12.5%}` → `m_C ∈ {20, 17, 13, 10, 8}`.
- `C = 12.5%` collapses to quintile (D2) — an endpoint diagnostic, EXCLUDED
  from selection so that the chosen D1 is a genuine cap test (amended
  pre-holdout-5, see Amendment 1 below). It is still reported as a construction.

### Deterministic cap selection (DEVELOPMENT ONLY — train then validation report)
For each candidate C, compute on dev-TRAIN (gate-active days, 25 bps):
`net_expectancy_bps` and `top5_share` (|top-5 gross symbol P&L| / |total gross|).

- **TRAIN rule:** a cap QUALIFIES iff `top5_share < 0.30` AND
  `net_expectancy_bps > 0`. Select the **largest** qualifying C (least dilution),
  from the set `{5%, 6%, 8%, 10%}` (12.5% endpoint excluded).
- If no C qualifies on both: select the largest C with `top5_share < 0.30`
  (diversification priority; economic result reported, may be ≤ 0).
- If none at all: D1 = C=5% used regardless, flagged.
- **VALIDATION is REPORT ONLY — no re-selection. Holdout-4 is never used for
  selection.**

> **Amendment 1 (2026-09-13, BEFORE any holdout-5 sight):** the original rule
> selected the largest qualifying cap across ALL candidates including the
> C=12.5% endpoint, which is weight-identical to D2 (quintile). Selecting it
> would make D1 ≡ D2 and the holdout-5 test vacuous as a diversified-vs-
> concentrated test. Amendment: drop the 12.5% endpoint from the choice set
> (it remains reported as a diagnostic construction). Dev-TRAIN outcome under
> the amended rule: qualifiers = C=8% (top5_share 0.103, exp +8.66 bps) and
> C=12.5% (excluded); largest remaining = **C=8% → m=13**. Frozen D1 for
> holdout-5. Nothing else in the protocol changes.

## Phase 3 — D2 control

**D2** = quintile equal weight (m=8, no cap) = `V1_QUINTILE_EQ`. No optimization.
Identical costs/assumptions as V1.

---

## Methods for Phases 4-11 (frozen)

- **Corpus:** DEVELOPMENT only (`data/alpha_v2/development_v2_panel.parquet`),
  gate-active dates under `composite_freeze.json` v2. P&L = close-to-close
  `fwd_ret_1` on dev (panel convention), identical to V1 dev evaluation.
- **Costs:** 25 / 50 / 100 bps/day, turnover = Σ|Δw| per day (2.0 at first
  deployment/re-entry). Gross → cost → net reported, never cherry-picked.
- **Metrics (12A):** active days, avg positions/side, turnover, gross cum %,
  net cum %, expectancy (net bps), PF, win rate, Sharpe, Sortino, MDD,
  worst/best day.
- **Concentration (12B):** max single-name |w|, Herfindahl = Σ|w|² over the
  gross book, top-1/3/5/10 gross P&L share, % active days with
  max|w| > 1.5×(1/m), average active positions, **leave-one-symbol-out** sign
  flips (fragile if any name flips the net sign).
- **Regimes (12C, diagnostic only — no new filters):** breadth state
  (G1 high/low, G6 rising/falling), dispersion state (G4 high/low),
  volatility (mkt_vol_20 terciles + panel `regime_bucket`).
- **Symbol/Sector (12D):** gross P&L contribution by symbol and by
  `vt_signal.sector_of`; market-cap bucket where a universe-cap snapshot exists
  (holdout-5; not available on dev).
- **Walk-forward (12E):** 4 contiguous windows (same boundaries as V1 dev).
- **Tail (12F):** full / winsorized_1pct / drop_1pct / drop_5pct (pre-defined).

## Phase 12-13 — Holdout-5 (frozen protocol)

- **Holdout-5 = new untouched corpus.** Universe: top-40 by Yahoo
  `marketCap` snapshot from a static POOL5 (runtime-asserted disjoint from the
  union of all used symbols: development + holdout + holdout_2 + holdout_3 +
  holdout_4, currently 226). Same selector/acquire/lock pipeline as holdout-4;
  single window 2014-01-01 → acquisition date; locked BEFORE evaluation.
- Holdout-4 is **NOT** reused as confirmation.
- **One-shot evaluation of frozen D1 + D2** (and V1 constructions as benchmark):
  net/expectancy/PF/MDD/Sharpe/Sortino, concentration suite, LOTO, cost stress
  25/50/100, regime + sector + symbol diagnostics.
- **Phase 14 decision:** A ROBUST DIVERSIFIED / B PROMISING-INSUFFICIENT /
  C SIGNAL SURVIVES-ECONOMICS FAIL / D STILL CONCENTRATION-FRAGILE /
  E FAILED TO REPLICATE / F COST-FRAGILE / G INCONCLUSIVE.
- **Phase 15:** paper-trading gate for `COMP3_STRATEGY_V2` only if holdout-5
  shows positive net expectancy, adequate sample, acceptable drawdown,
  acceptable concentration, positive under realistic costs, temporal robustness,
  no leakage. Otherwise **DO NOT PAPER TRADE**.

## Hard rule
This experiment NEVER claims "COMP3 works because Holdout-4 made +115%".
Holdout-4 failed confirmation on concentration. The question is whether the
COMP3 signal survives when no small set of names can dominate the economics.