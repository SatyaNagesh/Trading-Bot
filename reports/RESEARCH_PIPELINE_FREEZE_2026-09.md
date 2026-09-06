# RESEARCH PIPELINE FREEZE — 2026-09-06

**Status: FROZEN. From this instant onward, no methodological component below
may be changed.** Any violation invalidates the independent-holdout experiment.

---

## 1. Purpose

Lock the research stack so that an **independent out-of-sample holdout** can be
obtained and evaluated without contamination. This document freezes:

- the exact code (git hashes),
- the exact dataset / universe definitions,
- the exact methodology (features, strategies, execution, costs, metrics,
  splits, selection rules, decision rubric),
- the three data domains,
- the holdout evaluation protocol.

The cardinal rule is **REPLICATION, NOT DISCOVERY**: the holdout may only ever
be used to test already-frozen hypotheses. No feature, threshold, parameter,
strategy, or selection rule may be modified because of a holdout result.

---

## 2. Frozen code

| Component | Commit | Notes |
|---|---|---|
| Alpha discovery engine + report | `cc6c288` | `packages/research/{alpha_features,alpha_dataset,alpha_analysis,alpha_runner}.py` |
| Deep validation of vol_rel20@1 | `9e70300` | `packages/research/vol_validation.py` (checkpointed, 12 phases) |
| Historical data pipeline + expanded tournament | `4ad812a` | `packages/market/{data_ingestion,data_audit,data_pipeline,data_quality,data_split}.py`, `packages/research/{expanded_driver,candidates,driver,strategy,evaluation,execution,features,baseline,metrics}.py` |
| Strategy tournament (original) | `f23d69a` | first tournament framework + report |

**Working tree baseline:** `main` at `9e70300` (deep-validation merge point).
The freeze commit `FROZEN-COMMIT` (this document) adds only:
`reports/RESEARCH_PIPELINE_FREEZE_2026-09.md`,
`data/holdout/universe.json` (pre-registered holdout universe),
`packages/research/select_holdout_universe.py` (selection tool), and later
holdout manifests. It does **not** alter any frozen algorithm.

**Git tag:** `research-freeze-2026-09-06` → this commit.

---

## 3. Development dataset (must remain untouched)

- Source: yfinance 1.7.0, `interval=1d`, `auto_adjust=True` (splits+dividends).
- Universe: 49 NSE large-caps (NIFTY-50 family), Asia/Kolkata tz-aware.
- Range: 2014-01-01 .. 2026-09-04 (last available bar on freeze date).
- Provenance: `data/historical/manifest.json` (per-file sha256), `splits.json`,
  `audit.json`, `quarantine.json`, `failed.json`, `split_coverage.json` — all tracked.
- Raw parquet files are excluded from git (`.gitignore`: `data/`, `*.parquet`);
  reconstruction is reproducible from `manifest.json` + `data_ingestion.py`.
- Effective cross-sectional membership: 48 symbols (short-history symbol
  excluded per `symbols_with_full_history()`).

## 4. Frozen methodology (do not modify)

### 4.1 Alpha feature library (`alpha_features.py`, 21 features)
Causal features with definitions/timestamps in code: trend (sma20_gap, ema10_gap,
sma20_slope5, strength_20v50); momentum (roc20, rsi14, macd_hist_norm);
volatility (atr_pct, realized20, pctile_252); volume (vol_rel20, trend_10v50,
price_corr20); price structure (breakout20, lowdist20, bb_z20, vwap_gap20);
cross-sectional (xs_rel_str20, xs_mom_rank20); market context (mkt_ret_5d,
mkt_vol_20). Labels: `fwd_ret_{1,3,5,10,20}` strict-future.

### 4.2 Candidate strategies (`candidates.py` + `baseline.py`)
- **A_trend_following**: long EMA20>EMA50 & ADX(14)≥20 & ATR%>0 & vol_ratio≥1;
  flat when EMA20≤EMA50 or ADX<18.
- **B_momentum**: long RSI(14)∈(50,70)&MACD-hist>0&ROC5>0; short RSI∈(30,50)
  &MACD-hist<0&ROC5<0; flat on reversal.
- **C_breakout**: long close>Donchian20 upper & ATR%>0.005 & vol_ratio≥1.1 &
  EMA50 slope>0; flat close<Donchian mid or slope≤0.
- **D_mean_reversion**: long z≤−2 & RSI<30 & close<VWAP & ATR%<0.02; flat z≥0
  or RSI>50.
- **E_multi_factor**: composite of trend+momentum+volatility+volume+regime
  factors; long composite≥+2, short ≤−2.
- **autonomous_momentum** (baseline, reconstructed): long when flat &
  momentum(5)>0 & regime-compatible (trending/breakout/low_vol/unknown); exit
  when momentum<0.

Default params are in the constructor signatures; those exact params are frozen.

### 4.3 Execution & costs
One-bar fill delay (`execution.py`), same costs for every candidate:
slippage 0.001 + commission 0.0005 per side. PPD=1 (daily).

### 4.4 Metrics (`metrics.py`)
net_total_return_pct, expectancy_pct, win_rate_pct, profit_factor,
max_drawdown_pct, sharpe, sortino, trades n, 95% bootstrap CI on expectancy,
top-10%-net share. `MIN_OOS_TRADES = 30`.

### 4.5 Tournament selection rule (`expanded_driver.decision`)
INSUFFICIENT DATA if pooled OOS trades < 30; NO EDGE if expectancy≤0 or CI_lo≤0;
OVERFIT/FRAGILE if PF<1.2 or win<40% or param-positive-frac<0.5 or cost-fragile
>50% or regime-positive<0.5 or top10%share>0.90 or most-recent OOS window
negative (when ≥30 trades); else PROMISING-MORE DATA.

### 4.6 Splits (chronological, strict no-overlap)
- TRAIN: 2014-01-01 → 2023-01-01 (development; never scored)
- VALIDATION: 2023-01-01 → 2025-07-01 (selection sanity)
- FINAL-OOS: 2025-07-01 → 2026-09-04 (untouched)

### 4.7 Alpha discovery methodology (`alpha_runner.py`)
IC grid over 105 hyps (21 features × 5 horizons) → BH-FDR q≤0.10 on VALIDATION →
walk-forward (12 blocks; survival = same-sign ∧ |IC|≥0.005 ∧ one p<0.1) →
cost discipline (net > gross ⇒ COST-FRAGILE absent) → ranking labels
STRONG/BETTING-AGAINST/PROMISING-MORE DATA/REVERSED SIGNAL/UNSTABLE/COST-FRAGILE.

### 4.8 Deep-validation rubric (`vol_validation.py`, decision A–F)
A=REPLICATED ROBUST EDGE, B=PROMISING BUT INSUFFICIENT, C=FAILED TO REPLICATE,
D=NO EDGE, E=DATA QUALITY/METHODOLOGY PROBLEM, F=INCONCLUSIVE. Uses 12 phases:
temporal replication, quantile shape, symbol robustness, regime robustness,
outlier concentration, horizon curve, alternative volatility family,
cost/turnover ladder, randomization (300 sims × 3 nulls), selection-bias audit,
final holdout check, decision.

### 4.9 Frozen candidates for the holdout experiment
- Strategies: A_trend_following, B_momentum, C_breakout, D_mean_reversion,
  E_multi_factor, autonomous_momentum_baseline. (The expanded-tournament
  registry is frozen exactly as-is.)
- Alpha features: **vol_rel20** @ horizons {1,3,5} (finalists: @1) and
  **vol_trend_10v50** @ {1,3} (survivors of the alternative-family FDR).
  No other feature is eligible to be championed.

---

## 5. Data domains

| Domain | Contents | Go/no-go |
|---|---|---|
| DEVELOPMENT | `data/historical/` — 49 dev symbols, 2014→2026-09-04 (Sections 3,4) | Already used for discovery/selection; never re-scored for holdout claims |
| FROZEN HOLDOUT | `data/holdout/` — 60 NEW symbols, 2010-01-01→2026-09-04 (Sections 6,7) | UNTOUCHED until frozen pipeline is re-run; lock = manifest sha256 |
| FUTURE/PAPER | any bars ≥ 2026-09-05 (post-freeze) | Reserved; never mixed into DEVELOPMENT or FROZEN HOLDOUT |

HOLD OUT IS SACRED: no inspection during development, no optimization, no
re-testing of alternative rules after a result is seen, no live/paper trading,
no AlphaLedger integration, no copying of external strategies.

---

## 6. Holdout universe construction (pre-registered)

- File: `data/holdout/universe.json` (committed with this freeze).
- Rule (return-independent, captured at selection time):
  1. Static pool of 76 NSE large/mid-cap tickers, disjoint from the 49 DEV symbols.
  2. Ranked by Yahoo `fast_info['marketCap']` snapshot (`snapshot_utc`).
  3. Top 60 selected; ties alphabetized; symbols failing resolution are dropped
     **without substitution** (4 dropped: TATAMTRDVR.NS, LTIM.NS,
     TATAMOTORS.NS, ZOMATO.NS).
  4. No price-history return information was used at any selection step.

## 7. Holdout acquisition spec (frozen)

- Source: yfinance **1.7.0**, `interval=1d`, `auto_adjust=True`.
- Range: **2010-01-01 → 2026-09-05** (extended back 4 yrs beyond DEVELOPMENT,
  giving a genuinely-unseen longer period, PLUS a new-symbol universe).
- TZ: Asia/Kolkata (tz-aware index), columns open/high/low/close/volume.
- Store: `data/holdout/d1d/<SYMBOL_NS>.parquet`; manifest `data/holdout/manifest.json`
  with per-file sha256; `failed.json`, `audit.json`, `quarantine.json`;
  `splits.json` = exact copy of DEVELOPMENT splits (sec. 4.6).
- Quality gate: symbol kept iff daily bars ≥ 700 AND no gap diagnostic blocks
  it (`data_quality/quarantine_rows`). Drops recorded; never return-based.
- The **lock** = `data/holdout/manifest.json` checksums (tracked in git).

## 8. Holdout evaluation protocol (all frozen, no new selection)

1. Re-run `expanded_driver` semantics (Section 4.2–4.5) per symbol on the 60-symbol
   holdout corpus via identical frozen functions, data root injected only.
2. Pool validation+final_oos trades across holdout symbols → per-candidate
   replication table: net return, expectancy, PF, win rate, maxDD, Sharpe,
   Sortino, n trades, cost stress, param neighborhood, walk-forward, regime.
3. Alpha replication: rebuild the *holdout panel* with the frozen
   `alpha_dataset.build_panel` (store-root injected); report for
   **vol_rel20@{1,3,5}** and **vol_trend_10v50@{1,3}**: IC per split, quantile
   spread, sign stability, symbol breadth, regime consistency, randomization
   p-values, cost/turnover — identical phases to Section 4.8.
4. Replication verdict per candidate = Section 4.8 decision rubric (A–F).
5. If nothing replicates **the conclusion is non-edge**, not a licence to build
   a new strategy. Strategy construction is a separate future task, and only
   after a positive replication.

---

## 9. Prohibited changes after freeze

- No new/mutated features; no threshold/window/cost/criteria changes.
- No re-ranking of strategies on holdout; no picking winning names afterwards.
- No use of FUTURE/PAPER bars to "fix" a holdout miss.
- No modification of any file under `packages/research/` or
  `packages/market/` unless it is strictly additive orchestration that leaves
  frozen algorithm behavior bit-identical.
- No copying external strategies/code into the pipeline.
- No live or paper trading from holdout results.

## 10. Natural-history honesty note

On the freeze date the latest available trading bar is **2026-09-04** (NSE
closed 2026-09-05/06). A purely chronological hold-out
(same 49 symbols, later dates) therefore cannot be created today; it is
reserved as the FUTURE/PAPER domain and will become testable as bars accrue.
The FROZEN HOLDOUT created today is independent **cross-sectionally**
(new symbols) and **temporally** (2010–2013 pre-DEVELOPMENT years are unseen).