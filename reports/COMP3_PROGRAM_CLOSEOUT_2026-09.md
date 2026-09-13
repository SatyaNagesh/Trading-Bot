# COMP3 PROGRAM — CLOSE-OUT

**Date:** 2026-09-13
**Status:** COMP3 PROGRAM = **CLOSED**
**Paper-trading gate (Phase 15):** **CLOSED** — no paper trading, no live trading, no AlphaLedger.

---

## 1. Verdict

| Claim | Verdict |
|---|---|
| `COMP3_REVERSAL_BREADTH_DISP` scored positively in-development | Yes (see §5) |
| COMP3 Signal as a research finding | **interesting research finding** |
| COMP3 Strategy V1 (decile EQ, concentrated) | **REJECTED** |
| COMP3 Strategy V2 (D1_CAP8 diversified, frozen spec) | **REJECTED** |
| Independent holdout-4 (V1) | E CONCENTRATION-FRAGILE — NOT CONFIRMED |
| Independent holdout-5 (V2) | D STILL CONCENTRATION-FRAGILE — NOT CONFIRMED |
| Multiple-testing / honest negative | No reruns, no re-selection after sight, no parameter rescue |

COMP3 was rejected **not** because it lost money, but because its positive
economics are *concentration-dependent*: two independent, disjoint, untouched
holdout corpora both failed the pre-registered concentration gate (top-5 share
and/or leave-one-symbol-out sign flips). That is the expected outcome of a
faithfully executed pre-registration. The attractive holdout-5 raw economics
(§7) do **not** overturn the locked decision rule.

---

## 2. What was pre-registered (before any results)

- `reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md` (commit `e02cf28`) — signal
  freeze, D1 cap-candidate set {5,6,8,10,12.5}%, D2 quintile benchmark,
  Phases 4–15 protocol, A–G decision grades, paper gate, holdout rules.
- **Amendment 1** (commit `1b0d61e`, 2026-09-13, before any holdout-5 sight):
  exclude the C=12.5% endpoint from cap *selection* (weight-identical to the D2
  quintile); it stays a reported diagnostic. Selection then runs on {5,6,8,10}%.
- `reports/COMP3_STRATEGY_V2_SPEC_2026-09.md` (commit `73f61cd`) — frozen V2:
  PRIMARY `D1_CAP8` (m=13), control `D2_QUINTILE` (m=8), benchmark `V1_DECILE`
  (m=4); one-shot holdout-5 protocol.

## 3. Exact D1 selection rule (dev-TRAIN only)

Rule (Amended): on the **dev-TRAIN** split (388 active days), take the
**largest cap in {5,6,8,10}%** with `top5_share < 0.30` **AND** `expectancy > 0` bps.
The validation split is report-only and is never used for selection; holdout-4
and holdout-5 are never used for selection.

| Cap | m/side | train top5_share | train exp bps | qualifies? |
|---|---|---|---|---|
| 5% | 20 | 0.366 | +8.59 | no (top5 ≥ 0.30) |
| 6% | 17 | 0.594 | +9.36 | no (top5 ≥ 0.30) |
| **8%** | **13** | **0.103** | **+8.66** | **YES → chosen** |
| 10% | 10 | 0.392 | +5.15 | no (top5 ≥ 0.30) |
| 12.5% | 8 | 0.277 | +5.37 | ENDPOINT — excluded (Amendment 1) |

**Frozen D1 = C=8%, m=13 names/side, EW 1/13 (max |w| = 7.69%).**

## 4. Execution conventions (locked to holdout-4)

- Sizing: per-side top-m equal weight `1/m`; long = top-m, short = bottom-m.
- Turnover: pandas-aligned `|w_t − w_{t−1}|.sum()` with NaN-skip (union-sum
  positional turnover rejected as it overstated costs).
- P&L: dev study uses dev close-to-close `fwd_ret_1`; holdout evaluations use
  TRUE tradeable session returns `close_{t+1}/open_{t+1} − 1` on signal date `t`.
- Concentration: `top-k_share = |Σ top-k signed contribution| / |Σ net|`;
  `fragile = top5_share ≥ 0.50` OR any leave-one-symbol-out sign flip.
  A-grade concentration bar: `top5_share < 0.30` AND no LOTO sign flips.
- Cost stress: 25 / 50 / 100 bps per unit turnover.

## 5. Development study (deterministic, reproducible)

`packages/research/comp3_diversification.py` → `reports/comp3_diversification_results.json`
and `reports/COMP3_DIVERSIFICATION_RESEARCH_2026-09.md`.

| Construction | net% @25 | exp bps | top5 | MDD% | notes |
|---|---|---|---|---|---|
| V1_DECILE_EQ (m=4) | +50.4 | 10.55 | 0.575 | −30.4 | concentrated baseline |
| D2 quintile (m=8) | +46.9 | 9.18 | 0.259 | −12.2 | |
| D1_CAP5 (m=20) | +53.4 | 9.48 | 0.365 | −11.6 | |
| D1_CAP6 (m=17) | +60.0 | 10.47 | 0.561 | −11.5 | |
| **D1_CAP8 (m=13)** | **+60.8** | **10.73** | 0.450 | −11.4 | selected |
| D1_CAP10 (m=10) | +41.8 | 8.24 | 0.562 | −14.4 | |
| D1_CAP125 (m=8) | =D2 | — | 0.259 | — | endpoint diagnostic |

Walk-forward (4 contiguous windows, D1_CAP5 proxy): 3/4 positive. Tail robust
(full / winsorized / drop-1% / drop-5%). Determinism verified: a rerun produces
byte-identical JSON + report (see §9).

## 6. Holdout-5 universe + corpus (from real manifests)

- Used union recomputed from actual manifests = **228 symbols**
  (dev 49, H1 60, H2 39, H3 40, H4 40) — verified at runtime, not from memory.
- Selection: static tranche-5 pool, top-40 by Yahoo `marketCap` snapshot at the
  selection instant (no price/return info), zero overlap with the 228.
  Universe locked at commit `d6a26bf` BEFORE any download.
- Acquisition: 40/40 resolved, 2014-01-01 → 2026-09-11, `Asia/Kolkata`,
  auto-adjusted (splits + dividends) yfinance d1d, 108,300 bars.
- Audit: 39 WARN + 1 FAIL. **FSL.NS dropped** (784-day data hole; 0 bars in 2016)
  with NO substitution per protocol → **39 eligible**.
- **Lock: sha256 `13a1eeb11cac628b711b146efff1c0b89548c695ef8884c63790e12dbcba7833`**
  (= sha256 of manifest bytes; 39 symbols; 108,300 bars). Verified matching on
  every evaluation and in `verify_comp3_program.py`.

## 7. Holdout-5 one-shot result (reproduced byte-identical)

`packages/research/holdout5_strategy.py` (build restricted to the locked 39
eligible symbols; corpus bytes untouched; lock re-verified in-process).

| Constraint | D1_CAP8 (PRIMARY) | D2_QUINTILE | V1_DECILE |
|---|---|---|---|
| net% @25bps | **+67.89** | +47.73 | +50.69 |
| expectancy bps | **+6.07** | +5.14 | +6.68 |
| profit factor | **1.162** | 1.102 | 1.088 |
| MDD% | **−38.94** | −51.17 | −59.58 |
| win rate | **52.8%** | 49.6% | 54.2% |
| active days | 949 | 949 | 949 |
| positions (avg/side) | 13 | 8 | 4 |
| top5_share | 0.218 | 0.314 | 0.031 |
| LOTO sign flips | **14** | **14** | **14** |
| concentration_fragile | **TRUE** | **TRUE** | **TRUE** |

- Cost stress @100bps: D1_CAP8 net +65.36% (positive). Half-year tiles:
  15/26 positive. Pooled IC (rank, session-return) +0.0182, p=0.0011.
- **The exact same 14-symbol LOTO flip set appears in all three constructions**
  (HATSUN, LAURUSLABS, GODREJAGRO, NIACL, ASTERDM, BANDHANBNK, FINEORG,
  CREDITACC, RVNL, KPITTECH, HOMEFIRST, CRAFTSMAN, DEVYANI, DELHIVERY): the
  positive P&L on this universe is driven by a handful of names regardless of
  construction. Diversification (13/side vs 8/side vs 4/side) reduces but does
  NOT eliminate the fragility.

## 8. Decision — A–G grade and paper gate

Phase 15 gates on D1_CAP8 @25bps:

```
positive_net_expectancy   true
sufficient_sample         true
acceptable_drawdown       true
acceptable_concentration  FALSE   (LOTO sign flips on 14/39 symbols)
positive_under_costs      true
temporal_robustness       true
no_leakage                true
```

**Grade: D STILL CONCENTRATION-FRAGILE → NOT CONFIRMED.**
**Paper-trading gate: CLOSED. COMP3_STRATEGY_V2 is not paper-traded.**

## 9. Reproducibility + integrity (close-out audit)

`packages/research/verify_comp3_program.py` runs the full locked pipeline and
asserts byte-identity + corpus integrity. All checks PASS:

1. dev-study rerun → JSON + report byte-identical to commit `611bc17`;
2. holdout-5 `--evaluate` rerun → results/classification/report byte-identical;
3. `dataset_lock.sha256` == sha256(manifest bytes) == `13a1eeb…`;
4. all 40 d1d parquet checksums match their manifest entries;
5. holdout-5 selected (40) and eligible (39) disjoint from the 228 real used symbols;
6. audit drop exactly FSL.NS; eligible = 39;
7. decision gates as in §8.

Repository hygiene: `git status` clean after all reruns; COMP3 commits touched
only the four research scripts plus reports/data (no changes to trading, paper
runtime, risk engine, deployment guards, or other Alpha Discovery results).
Holding the full test suite: 542 passed; 7 pre-existing failures in
`candidates`/`data_quality`/`indicators` modules that the COMP3 program never
modifies (documented, unrelated to this program, present on the base commit).

## 10. Preservation

All COMP3 artifacts are committed and preserved as a completed research
program: pre-registration (+Amendment 1), dev engine + study, dev results JSON,
V1 freeze/spec, V2 spec, holdout-4 confirmation (reference only, not
confirmation), holdout-5 selector/acquire/evaluator, holdout-5 locked corpus +
results, and this close-out. No COMP3 V3, no re-interpretation of the locked
holdout-5 result, no further COMP3 research.