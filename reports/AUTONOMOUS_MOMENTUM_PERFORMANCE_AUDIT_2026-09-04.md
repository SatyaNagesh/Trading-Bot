# AUTONOMOUS_MOMENTUM — PERFORMANCE AUDIT

**Date:** 2026-09-04 (market session AND audit date)
**Strategy:** `autonomous_momentum`
**Scope:** Backtest, walk-forward, Monte Carlo, sensitivity, live/paper comparison, critical validation, profitability classification.
**Pipeline used:** the project's existing validation pipeline only. **No strategy logic, parameters, thresholds, confidence, regime rules, optimizer, risk, or execution behavior was modified. No live trading was enabled. Paper mode maintained.**
**Audit result (bottom line):** A validation-pipeline **credibility problem** exists. There is **no verifiable historical performance evidence** for `autonomous_momentum` anywhere in this repository, because the required validation pipeline was never run (and in places cannot run as written).

---

## 1) BACKTEST

**Status: NOT RUN for `autonomous_momentum`. No results exist.**

Evidence:
- The only runnable backtest path in the CLI — `apps/cli/main.py` `backtest run` — hard-codes **`sma_crossover`** (`packages/indicators/api.sma`). There is **no CLI or engine wiring that backtests `autonomous_momentum`**.
- `autonomous_momentum`'s live decision logic lives in `packages/signals/optimizer.py` (`SignalOptimizer`) and `packages/core/scheduler.py` (~lines 505-544: `classify_regime` → direction → `confidence = 0.60 + min(momentum, 0.30)` → `optimize`). It is **never wired into the backtest engine**.
- A repository-wide search for stored backtest results (json/pkl) returned **nothing**.
- The only historical dataset is `data/cache/parquet/{RELIANCE,TCS}_NS.parquet` (≈376/382 rows, 1-minute bars, ≈3.5 weeks of intraday; RELIANCE runs 2026-08-03→08-24 + 09-04) — far short of the spec's minimums (`docs/33_BACKTEST_ENGINE_SPEC.md`: ≥500 train bars / ≥200 test / ≥500 trades). No daily history exists.
- The engine (`packages/backtesting/engine.py`) hard-codes `MarketRegime.RANGING` and fills at close with `commission=0.0005, slippage=0.001, spread=0.0002` (from `BacktestConfig`) — but only ever exercised for `sma_crossover`.

**No Sharpe, return, win-rate, drawdown, trade-count, or expectancy number exists to report for `autonomous_momentum`. Any such figure would be fabricated; none is stated here.**

---

## 2) WALK-FORWARD

**Status: NEVER RAN — and CANNOT RUN as written.**

Evidence:
- `packages/backtesting/advanced.py` line 11 does `from packages.backtesting.report import BacktestReport, compute_metrics` → **`ImportError: cannot import name 'BacktestReport' from 'packages.backtesting.report'`** (`report.py` only defines `generate_summary`/`generate_csv`; neither `BacktestReport` nor `compute_metrics` exists).
- Additionally `advanced.py` calls `BacktestEngine(initial_capital=Decimal(...))` and `engine.run(train_bars, strategy)` — both signatures mismatch the actual engine (`config=BacktestConfig(...)`; async `run(bars: dict[str, list[Bar]])`).
- Consequence: `WalkForwardAnalyzer` and `MonteCarloSimulator` are **unimportable**; the walk-forward analysis **has never produced outputs** for any strategy, including `autonomous_momentum`.

**No walk-forward windows, no out-of-sample segment, no rolling performance exists. UNKNOWN / NEVER RAN.**

---

## 3) MONTE CARLO

**Status: NEVER RAN (same root cause as §2).**

Evidence:
- `MonteCarloSimulator` lives in the same broken `advanced.py` module and is equally unimportable due to the `BacktestReport` ImportError.
- The `docs/33_BACKTEST_ENGINE_SPEC.md` design (10,000 MC iterations) is not implemented; no MC run was ever executed.

**No simulation outcome distribution, confidence band, or probability-of-loss exists. UNKNOWN / NEVER RAN.**

---

## 4) SENSITIVITY

**Status: NOT PERFORMED (robustness only; no search for best params was attempted or is reported).**

Evidence:
- No `sensitivity` / `SensitivityAnalyzer` / param-ranking module exists in the codebase (grep hits for `sensitivity` only appear in lifecycle/ops docs, not a runnable analysis).
- Per constraints, sensitivity was treated strictly as **robustness surveillance**, and since **no baseline backtest exists to perturb**, there is nothing to measure.

**UNKNOWN / NOT PERFORMED.** (No parameter search was conducted; the task forbids optimization.)

---

## 5) LIVE / PAPER COMPARISON (historical expected vs Sept 4 actual)

**`autonomous_momentum` operates in PAPER mode. It is active. Runtime is under systemd PID 637745 (restarted from 103688 earlier this session); live API :8000 is up and healthy (Phase 8/9: 67/67, Phase 10: 13/13 tests green; checkpoint integrity OK).**

### 5a) Historical expected signal frequency
- **There is no historical expected signal frequency, because `autonomous_momentum` was never backtested/walk-forwarded (§1–2).** Therefore there is **no model-predicted baseline** to compare Sept 4 against. This absence is itself the headline finding.

### 5b) Sept 4 actual behavior
- Live optimizer stats (post-restart, in-memory) read `{received:0, accepted:0, suppressed:0, history_len:0}` and scheduler `cycle_stats {cycles:0, data_events:0, signals_generated:0}`. **These counters do NOT reflect the real session**: they were **reset by the runtime restart** (new PID after market close) and are non-persisted cycle counters. The authoritative record is the persisted prior-session report.
- The prior-session report `reports/LEVEL3_SESSION_2026-09-04.md` documents the Sept 4 session in detail: the scheduler ran the research + signal path **every cycle (114–115 research-pipeline runs)**, calling `SignalOptimizer.optimize()` per symbol over live cached minute-bars (357 bars/symbol delivered through 15:11 IST), and produced **0 accepted** signals → 0 orders / 0 fills / 0 trades. P&L flat at **1,000,000**, `total_pnl = 0.0`. `order_journal.jsonl` shows no 09-04 entries (last activity 08-31); `trades_history: []`.
- **Cause of the zero (as documented, with no code changes made):** the strategy's momentum/round-trip criteria did not **emit an accepted entry** on the day's live data. This is a **signal-generator / entry-criterion observation — NOT a suppression event and NOT an infrastructure failure** (live feed, gate, regime handling, and safety all worked; regime did not gate to "degraded"; `autonomous_momentum` remained `active` in `data/strategies.json`).
- **No attempt was made to force the numbers to match any expectation.** None exists.

### 5c) Comparison verdict
- Header "expected" is **undefined** (no historical backtest ⇒ no expected rate).
- Actual Sept 4 = **0 accepted trades**. The gap between "undefined expectation" and "zero realized" cannot be attributed to strategy under-performance — it is attributable to **the absence of a validation baseline** plus a zero-trade observation day.
- A single zero-trade session is **not** meaningful statistics and is not evidence of profitability or non-profitability.

---

## 6) CRITICAL VALIDATION (look-ahead / leakage / fills / costs / slippage / survivorship)

For `autonomous_momentum`: **UNKNOWN — NOT APPLICABLE**, because no backtest of the strategy exists, and the broken `advanced.py` walk-forward/MC could not have masked leakage (it cannot even import).

For the only backtest that exists in the repo (`sma_crossover`):
- **Look-ahead / leakage:** UNKNOWN (not audited for `sma_crossover`; not part of this scope).
- **Fills:** engine fills at **close** and **hard-codes `MarketRegime.RANGING`** for every bar — unrealistic fill/regime assumptions; not verified against live fill/latency.
- **Costs / slippage:** `BacktestConfig` defaults `commission=0.0005, slippage=0.001, spread=0.0002`. Whether these match live `PaperBroker` fills / API latency is **UNKNOWN/unverified**.
- **Survivorship:** the parquet set is a hand-picked pair (RELIANCE/TCS) with no delisting/selection audit — **UNKNOWN**.
- **For `autonomous_momentum` specifically:** none of the above apply because the strategy was never backtested. Marking each **UNKNOWN** is therefore honest rather than a gap in measurement.

---

## 7) PROFITABILITY CLASSIFICATION

**Classification: E — THE VALIDATION PIPELINE HAS A CREDIBILITY PROBLEM.**

Rationale (assign one, and only one, of A/B/C/D/E; here **E**):
- **A** (proven profitable out-of-sample) — **NO**: no out-of-sample evidence exists.
- **B** (promising but needs more time) — **NO**: there is no validated performance at all.
- **C** (not profitable / flawed) — **NO**: cannot say "not profitable" without a valid test.
- **D** (inconclusive, insufficient data) — **NOT FULLY**: the deeper issue is that the pipeline needed to produce the data is incomplete/broken.
- **E** — **YES**: the strategy had (i) the only runnable backtest hard-coded to `sma_crossover`; (ii) walk-forward + Monte Carlo **unable to import** (`BacktestReport` ImportError); (iii) **no stored results** anywhere; (iv) only ~3.5 weeks of intraday history vs the spec's explicit minimums; and (v) the live decision path never wired into the engine. **You cannot trust any backtest numbers for `autonomous_momentum` because there are none; and the numbers that could be produced today cannot be trusted until the pipeline is fixed.**

---

## Evidence-Based Next-Step Recommendation (ONE)

**Build and wire a correct validation path for `autonomous_momentum`, and accumulate genuine out-of-sample history — do not trust or act on any current result.**

Concretely, the single highest-value step is:
1. **Fix the broken validation code** so results can actually be produced: resolve the `BacktestReport`/`compute_metrics` ImportError in `packages/backtesting/advanced.py` and repair the `BacktestEngine(config=...)` / async `run(bars: dict)` signature mismatches so `WalkForwardAnalyzer` and `MonteCarloSimulator` can run.
2. **Wire the live decision path into the engine** — expose `autonomous_momentum`'s `SignalOptimizer`/scheduler candidate logic (regime → direction → `confidence = 0.60 + min(momentum, 0.30)` → optimize) as a backtestable strategy, alongside the existing `sma_crossover` path.
3. **Accumulate sufficient data** (daily or ≥ the spec's 500-train/200-test/500-trade intraday) and run a **walk-forward + Monte Carlo + sensitivity (robustness)** campaign, then soak out-of-sample in PAPER.

Until steps 1–3 produce a validated, out-of-sample result, **no profitability claim may be made for `autonomous_momentum`**, and Sept 4's zero-trade session should be treated as an **observation**, not evidence of anything.

---

## Appendix — Evidence File Map

| Artifact | Path | Finding |
|---|---|---|
| Walk-forward/MC source (BROKEN) | `packages/backtesting/advanced.py` | `ImportError: BacktestReport`; signature mismatch |
| Backtest report module | `packages/backtesting/report.py` | lacks `BacktestReport`/`compute_metrics` |
| Engine | `packages/backtesting/engine.py` | hard-codes RANGING + close fill; async `run(dict)` |
| CLI backtest | `apps/cli/main.py` | only `sma_crossover` wired |
| Strategy spec (intended) | `docs/33_BACKTEST_ENGINE_SPEC.md` | design unmet |
| Only historical data | `data/cache/parquet/{RELIANCE,TCS}_NS.parquet` | ~3.5wk intraday, 1-min |
| Live decision logic | `packages/signals/optimizer.py`, `packages/core/scheduler.py` | never in engine |
| Sept 4 session record | `reports/LEVEL3_SESSION_2026-09-04.md` | 0 accepted / 0 trades; cause = entry criteria, not infra |
| Stored results | repo-wide search | none |
