# AUTONOMOUS_MOMENTUM — HISTORICAL REPLAY & DEEP ANALYSIS

**Date:** 2026-09-04
**Strategy:** `autonomous_momentum` (active, PAPER only — no live trading, no paper-behavior change, no optimization in this audit)
**Method:** Faithful **causal, bar-by-bar replay** that reuses the exact functions the live paper runtime calls (`SignalOptimizer.classify_regime`, `SignalOptimizer.optimize`, `get_cached_bars`), over the repository's **existing** local historical data. No reimplementation, no look-ahead, no fabricated results.
**Pipeline deliverable:** The previously-broken validation pipeline (`advanced.py` `BacktestReport` ImportError) was **fixed** and verified importable + executable against the real `BacktestEngine`.

---

## 1. EXECUTIVE SUMMARY

**Bottom line: `autonomous_momentum` has NEVER actually run a genuine, market-anchored historical backtest or replay — before this task.**

- The only `autonomous_momentum` order history in the durable journal is a **test-artifact flood on Saturday 2026-08-29** (2,412 events / 402 orders at fixed, static fill prices; NSE closed that day) — a forced/scripted validation run, **not** genuine chart analysis.
- The **one real live session** on **Friday 2026-09-04** evaluated live 1-minute data and produced **zero** accepted signals / zero orders (confirmed by empty checkpoint + `grep -c "2026-09-04"` = 0 in `order_journal.jsonl`).
- A faithful causal replay of the strategy's actual decision code over the existing data shows **why**: the entire acceptance gate collapses to **`classify_regime() == "trending"`**, and on this data the regime is **`ranging` 92.9%** of the time → ~everything is suppressed as `regime_incompatible_ranging`.

**Classification: A (HISTORICALLY STRONG AND CURRENTLY SUPPRESSED) — NO.** See §25. The honest, evidence-based classification is **D / F** (insufficient data; historical analysis of the intraday strategy was effectively never run), with the caveat that the intraday signals that *were* emitted on 09-04 were **net losers**.

---

## 2. DID HISTORICAL REPLAY ACTUALLY HAPPEN BEFORE THIS TASK?

**NO VERIFIED HISTORICAL REPLAY FOUND.** Evidence:

| Check | Finding |
|---|---|
| Stored backtest/replay results (json/pkl) | **None anywhere** in repo (`advanced.py` walk-forward/MC had no outputs) |
| `advanced.py` (walk-forward/MC) | Was **unimportable**: `ImportError: cannot import name 'BacktestReport' from 'packages.backtesting.report'` (report.py lacked `BacktestReport`/`compute_metrics`) — **never ran** |
| CLI backtest path | `apps/cli/main.py backtest run` hard-codes **`sma_crossover`** only; no `autonomous_momentum` path |
| `autonomous_momentum` in backtest engine | **Never wired** — its logic lives only in `scheduler._generate_validate_signals` + `SignalOptimizer` (live path), not in engine strategy DSL |
| Signal journal (`data/signal_journal.jsonl`) | **Does not exist** — deployed post-close on 09-04; never recorded a candidate |
| Order journal (`data/order_journal.jsonl`) | Only `autonomous_momentum` activity = **08-29 (Sat) test flood** at static prices; **zero** 09-04 entries |
| Checkpoint | `trades_history: []`, `positions: {}`, `total_pnl: 0.0` |

The strategy was **never run against historical charts** to produce genuine market-anchored decisions.

---

## 3–7. EXACT HISTORICAL DATA ANALYZED

**Data source:** existing local cache `data/cache/parquet/{RELIANCE_NS,TCS_NS}.parquet` (loaded via the project's own `get_cached_bars`).

### Symbols
- `RELIANCE.NS` (376 rows)
- `TCS.NS` (382 rows)

### Timeframes — TWO distinct datasets present
1. **Daily** bars (00:00 IST midnight): RELIANCE **16 trading days** (2026-08-03 → 2026-08-24); TCS **22 days** (2026-07-27 → 2026-08-25).
2. **Intraday 1-minute** bars: **only on 2026-09-04**, 360 bars/symbol (09:15 → 15:14 IST). **No 1-min history exists for any earlier date.**

### Date ranges / bar counts
| Symbol | Earliest | Latest | Daily bars | 1-min bars (09-04) | Total |
|---|---|---|---|---|---|
| RELIANCE.NS | 2026-08-03 00:00+05:30 | 2026-09-04 15:14+05:30 | 16 | 360 | 376 |
| TCS.NS | 2026-07-27 00:00+05:30 | 2026-09-04 15:14+05:30 | 22 | 360 | 382 |

### Missing-data gaps / timezone
- Cache index: tz-aware `datetime64[ns, Asia/Kolkata]`.
- Intraday data covers **only one session** (09-04); earlier sessions have only daily closes. There is **no multi-day 1-minute history** — a hard limit on any intraday backtest.
- No daily dataset beyond ~1 month; far short of the `docs/33_BACKTEST_ENGINE_SPEC.md` minimums (500-train/200-test bars, 500 trades).

> **Honest note:** Replaying the 1-minute-oriented strategy on **daily** bars is a **category error** that I ran only to illustrate the mechanism. The **meaningful, bot-consistent replay is the 09-04 intraday one** (the only data the live bot ever consumed at its native 1-min timeframe).

---

## 8. WHAT THE STRATEGY ACTUALLY DECIDES (THE REAL DECISION PATH)

The live scheduler (`packages/core/scheduler.py::_generate_validate_signals`, lines 481–611) + `SignalOptimizer.optimize` (lines 34–102). For each symbol at each evaluation:

1. `recent_bars(symbol)` → `get_cached_bars(symbol, max_rows=120)` = tail-120 of the merged cache.
2. `regime = SignalOptimizer.classify_regime(bars)` (SMA10-vs-SMA20 slope over `bars[-60:]`; vol > 0.05 → `volatile`; slope > 0.005 → `trending`; else `ranging`; <20 closes → `unknown`).
3. `direction = "long"` when flat (hard-coded round-trip).
4. `confidence = round(0.60 + min(|price-last_close|/last_close, 0.30), 4)` — **always ≥ 0.60**.
5. `optimizer.optimize({long, confidence, ...}, strategy={status:"active"}, regime)`.

**The optimizer's acceptance reduces to the regime gate:** for `direction=long`, only `trending` allows long; `ranging`/`volatile`/`crisis` allow only `neutral` → suppress `regime_incompatible_<regime>`. **`unknown` passes** (no compat entry). Confidence (≥0.60) is **never** the binding floor (MIN_CONFIDENCE=0.55).

**⇒ The single lever that determines accept/suppress is `classify_regime()=="trending"`** (for a trading-enabled long strategy).

---

## 9–10. FAITHFUL CAUSAL REPLAY — FULL SIGNAL FUNNEL

Replay method: walk the full merged bar list chronologically; at each bar `t`, feed the last-120 causal window (matching `recent_bars` semantics) into the identical `classify_regime` + `optimize` calls. **No future bars used at any decision.**

### Combined funnel (both symbols, all bars, status=active)
| Stage | Count | % |
|---|---|---|
| RAW CANDIDATES evaluated | **756** | 100% |
| → regime = `trending` (⇒ ACCEPTED) | **54** | 7.1% |
| → regime = `ranging` (⇒ SUPPRESSED) | **702** | 92.9% |
| → confidence below floor | **0** | — |
| → strategy-status gate reject | **0** | — |
| → would-be orders (accepted) | **54** | (see caveat §10b) |

All 702 suppressions were `regime_incompatible_ranging`. **This is where signals disappear: the regime classifier.**

### 9b. Per-symbol
| Symbol | Candidates | Accepted | Suppressed | Suppression reasons |
|---|---|---|---|---|
| RELIANCE.NS | 375 | 21 | 354 | `regime_incompatible_ranging` ×354 |
| TCS.NS | 381 | 33 | 348 | `regime_incompatible_ranging` ×348 |

### 10a. The meaningful split — 09-04 intraday (1-min)
| Symbol | Candidates | Accepted | Suppressed | Regime mix |
|---|---|---|---|---|
| RELIANCE.NS | 360 | **6** | 354 | `ranging` 354, `trending` 3, `unknown` 3 |
| TCS.NS | 360 | **12** | 348 | `ranging` 348, `trending` 12 |
| **Total 09-04** | **720** | **18** | 702 | — |

### 10b. Daily bars (Aug) — illustrative only, NOT a valid intraday backtest
Because the strategy is 1-min-native and daily bars give <20 in-window closes early on, `classify_regime` returned **`unknown`** for the first ~15 (RELIANCE) / ~18 (TCS) daily bars — and **`unknown` passes the regime gate**, so the strategy would "accept LONG" on nearly every early daily bar at confidence 0.60. This exposes a **real quirk**: the `unknown` regime is a **silent acceptance path**, not a reject. This is diagnostic of the fragility of the gate, not evidence of profitability, and is flagged under §23.

---

## 11. HYPOTHETICAL (RE-CONSTRUCTED) TRADES — FORWARD EVALUATION

For every ACCEPTED candidate, entry at `close` (signal bar), exit at close `+20` bars later (strictly forward, causal). Conservative assumptions: **slippage 0.1% one-way + 0.1% round-trip txn cost** (total ~0.2% per round trip).

**09-04 intraday accepted (HISTORICAL HYPOTHETICAL / OUT-OF-SAMPLE RESULT):**
| Symbol | Accepted | With outcome | Wins | Win rate | Avg net | Sum net |
|---|---|---|---|---|---|---|
| RELIANCE.NS | 6 | 6 | 1 | 16.7% | **-0.33%** | -2.00% |
| TCS.NS | 12 | 12 | 0 | **0.0%** | **-0.87%** | -10.40% |
| **Total 09-04** | **18** | **18** | **1** | **5.6%** | **-0.69%** | **-12.4%** |

The TCS 09-04 "trending" entries at 09:15–09:28 were **all losers** (fwd20 net −0.3% to −1.5%). The RELIANCE 09:57–09:59 trending entries were also losers. Net: **the intraday signals the strategy would have emitted on 09-04 lost money.**

---

## 12–13. SUPPRESSED-SIGNAL COUNTERFACTUAL (did the filter reject good or bad?)

For every SUPPRESSED candidate, compute the same forward-20-bar net return WITHOUT changing the decision (diagnostic only):

| Symbol | Suppressed w/ outcome | Counterfactual avg net | Counterfactual win rate |
|---|---|---|---|
| RELIANCE.NS | 334 | **-0.14%** | 8.7% |
| TCS.NS | 328 | **-0.27%** | 1.2% |

**Comparison:**
- **Accepted** avg net ≈ **-0.69%** (09-04 intraday); **Suppressed** avg net ≈ **-0.14%** to **-0.27%**.
- Both are **negative** on 09-04. The `regime_incompatible_ranging` filter is **not** rejecting obviously-profitable opportunities (suppressed were also losers), but it is also **not** saving the strategy from losses on this single day — it simply keeps it mostly flat. On 09-04 alone, **suppression avoided larger losses** but neither set showed an edge.

> Single-day sample → no profitability conclusion (see §14–18).

---

## 14–18. HISTORICAL P&L / WIN RATE / PROFIT FACTOR / EXPECTANCY / DRAWDOWN

**These metrics are reported ONLY for the faithful 09-04 intraday hypothetical outcome — the only genuine intraday replay — and are explicitly NOT profitable-proof (n tiny, single session).**

| Metric | 09-04 intraday hypothetical |
|---|---|
| Signals (accepted) | 18 |
| Trades reconstructed | 18 |
| Winning / losing | 1 / 17 |
| **Win rate** | **5.6%** |
| Gross P&L (sum net) | **-12.4%** (aggregate across 2×5-share hypothetical books) |
| Profit factor | < 1 (losses dominate) |
| Expectancy (mean net/trade) | **-0.69% per trade** |
| Max drawdown | not meaningful (flat single-day book; see caveat) |
| Sharpe / Sortino | **not computed** — sample is a single session, not statistically meaningful |

**INSUFFICIENT SAMPLE SIZE FOR PROFITABILITY CONCLUSION.** One trading day, 18 hypothetical fills, no independent out-of-sample validation. These numbers are diagnostic, NOT a claim the strategy "loses" or "wins."

---

## 19. SEPTEMBER 4, 2026 — SPECIFIC INVESTIGATION

**Ground truth (durable record):** `grep -c "2026-09-04" data/order_journal.jsonl` = **0**; checkpoint `trades_history: []`, `total_pnl: 0.0`. The LEVEL3_SESSION report documents 114–115 research-pipeline runs and **0 accepted** signals.

- **Symbols analyzed:** RELIANCE.NS, TCS.NS.
- **Timeframe:** 1-minute (360 bars/symbol, 09:15→15:14 IST).
- **Regime detected:** predominantly **`ranging`** (702 of 720 intraday candidates); brief `trending` (TCS 09:15–09:28; RELIANCE 09:57–09:59) and early `unknown`.
- **Confidence:** every candidate = **0.60** (momentum term ≈ 0 on 1-min closes and capped at 0.30; floor is 0.55).
- **Candidates:** 720 (2 symbols × 360 1-min bars). **Accepted:** 18 (by literal per-bar replay). **Suppressed:** 702.
- **Suppression reasons:** `regime_incompatible_ranging` ×702 (100% of suppressions).

**Were there genuinely no opportunities, or did software prevent signals?**
- The **software did not crash or block the pipeline** — it evaluated data every cycle (live feed confirmed at A4/A6). 
- The **strategy's regime gate** (only `trending` → long) is what suppressed almost everything on 09-04; the market was intraday-ranging that day. So at the **decision-code level** it was "mostly no opportunity" (range), and at the literal minute-by-minute extreme it would have fired 18 (all losers) — **not** an infrastructure outage.
- There is a **documented divergence** between the live run (which sampled at ~60s cycles and reported 0 accepted) and a literal every-minute replay (18 accepted). This is explained by **cycle sampling + exact cache-window timing**, not a logic difference. Both agree on the dominant cause: **regime suppression** (`ranging` → none accepted, in the live run; → promoted edges lost money, in the minute-by-minute replay).

---

## 20. VALIDATION / DATA CREDIBILITY AUDIT

| Check | Result |
|---|---|
| Look-ahead / future-candle leakage | **NONE in replay** — tail-120 causal window, forward returns use only bars after entry (verified in code). |
| Future labels | NONE used. |
| Timestamp alignment / timezone | tz-aware Asia/Kolkata; daily-vs-intraday mix is a real semantic wrinkle (documented), not silent corruption. |
| Duplicate candles | `validate_bars` dedups; cache dedups by timestamp keep-last (`_merge_intraday_into_cache`). |
| Missing candles | **Yes — the major limitation**: no multi-day intraday history; only one intraday session + ~1 month daily. |
| Unrealistic fills / zero slippage | **Flagged:** replay uses optimistic `close` fills; real execution relies on the canonical pipeline (idempotency/risk/flip-guard/broker). Engine fills at close with hard-coded `RANGING` market context — unrealistic for a momentum intraday strategy. |
| Transaction costs | Conservative 0.1% slippage + 0.1% txn assumed; the live `BacktestConfig` defaults (commission 0.0005, slippage 0.001, spread 0.0002) are not applied in this replay. |
| Survivorship bias | Not applicable to a 2-symbol hand-picked cache; acknowledged as selection, not a bias-free universe. |
| Train/validation/test contamination | N/A — no tuning was performed (task forbids optimization). |
| Signal-ts vs execution-ts | Replay fills at signal-bar close; real live path fills at next pipeline execution. |

**Result: the REPLAY CODING is credible (no look-ahead found), but the DATA and STATISTICAL BASE are insufficient to support any profitability conclusion.** The engine↔candidate-DSL incompatibility (`MarketContext` passed where a dict `ctx` is expected) — separately fixed/worked-around in the walk-forward harness — is a pre-existing integrity issue that prevented the strategy from ever being meaningfully backtested.

---

## 21. ROOT CAUSE OF SEPT 4 ZERO ACTIVITY

**Not an outage, not a suppression-by-risk, not low confidence.** The cause is:

**`SignalOptimizer.classify_regime` returned `ranging` for essentially the entire 09-04 intraday session**, and `autonomous_momentum`'s long-only candidate is suppressed in a `ranging` regime (`regime_incompatible_ranging`). Confidence was always 0.60 (above floor); status was `active`; the pipeline ran every cycle. With a range-bound session, the strategy's trend-following gate correctly stands aside → **0 orders**.

Underlying the gate: the signal's confidence is **effectively constant (0.60)** because the momentum term is tiny on 1-min moves, so the regime classifier is the **only** discriminator — making the whole strategy a de-facto **1-min "trending-regime" filter**.

---

## 22. WALK-FORWARD / MONTE CARLO / SENSITIVITY (now that pipeline is fixed)

- **Pipeline status after this task's fix:** `advanced.py` **imports** (`BacktestReport`, `compute_metrics` added; `WalkForwardAnalyzer`, `MonteCarloSimulator`, `MultiAssetBacktest` importable) and **runs** against the real `BacktestEngine` (verified: 6 walk-forward windows executed on live cache data via `sma_crossover`).
- **Walk-forward for `autonomous_momentum`:** cannot be meaningfully run — the strategy is not wired into the engine DSL and there is no genuine intraday multi-date sample. The 16–22 daily bars / 1 intraday session is **far below** any credible walk-forward (≥ hundreds of bars).
- **Monte Carlo:** tool runs (1000 sims, horizon 20) on daily log-returns: RELIANCE prob_loss 0.57 (from 16 daily bars), TCS prob_loss 0.53 (22 bars). **Statistically meaningless** — a ~1-month sample cannot estimate drift/vol. Reported only to prove the tool executes.
- **Sensitivity:** **not performed** — no baseline exists to perturb, and the task forbids optimization. Robustness testing (not param-fitting) is the correct future use.

**INSUFFICIENT SAMPLE SIZE FOR PROFITABILITY CONCLUSION** applies to all three.

---

## 23. CREDIBILITY SUMMARY AND CAVEATS

1. **The only real intraday evidence is one session (09-04).** Any win-rate/P&L from it is a single-day observation, not a statistical result.
2. **Daily-bar replay is illustrative, not valid** (wrong timeframe semantics + `unknown`-regime silent acceptance).
3. **Engine-vs-candidate mismatch** (`MarketContext` vs dict `ctx`) was present and is the reason candidate strategies never ran cleanly through the engine; it was worked around in the walk-forward harness, not hidden.
4. **Optimistic fills in replay** — shown only to characterize what the code *would* decide; not a record of real fills.
5. **08-29 paper orders** (402 static-price test orders, NSE closed) are **test artifacts**, excluded from any performance reading.

---

## 24. DIRECT ANSWERS TO THE TEN CRITICAL QUESTIONS

1. **Did `autonomous_momentum` actually analyze historical charts?** Before this task: **NO** genuine, market-anchored historical replay. Only a forced test flood (08-29, static prices) and one live session (09-04, evaluated but 0 orders).
2. **What exact dates did it analyze?** Live: **2026-09-04** (1-min). Test-flood: **2026-08-29** (Sat, static). No dated replay before today.
3. **Which symbols / timeframes?** RELIANCE.NS, TCS.NS; live at **1-minute**; older data only **daily**.
4. **How many signals?** Live 09-04: 720 candidates evaluated; **0 placed in live**; literal per-minute replay would have accepted **18**.
5. **What did it decide per signal?** Suppress long on `ranging` (702 of 720); accept long on `trending`/`unknown`. Confidence always 0.60.
6. **Would the hypothetical trades have made/lost money?** The 18 accepted (09-04 replay) were **net losers** (-12.4% aggregate; win rate 5.6%).
7. **Which historical dates were successful?** **None verifiable** — single session; no successful intraday outcome demonstrated.
8. **Which dates were failures?** 09-04 accepted windows lost; 08-29 is a test artifact (not a performance signal).
9. **Is the evidence statistically credible?** The **coding is clean (no look-ahead)** but the **sample is far too small / data too sparse to be statistically credible**.
10. **Continue or replace/improve?** Do **not** replace on this evidence, but do **not** trust any performance. The strategy is effectively a 1-min "trending-regime" filter with near-constant confidence; it needs a **real, multi-session intraday history + proper wiring into the engine** before any profitability judgement is justified.

---

## 25. FINAL CLASSIFICATION

**D — INSUFFICIENT HISTORICAL DATA** (with elements of **F — INCONCLUSIVE** and a clear `E — pipeline broken` root cause that was this task's fix).

- `autonomous_momentum` historical replay effectively **never ran** before this task (§2).
- The validation pipeline that would have produced it was **broken** (`advanced.py` ImportError + engine/DSL mismatch) — **now fixed and verified**.
- The only usable intraday history is **one session (09-04)**, on which the strategy's regime gate suppressed ~all activity and the few would-be signals lost money — but **18 hypothetical fills is not a profitability statistic** and the older data is daily-only.

---

## RECOMMENDED NEXT ENGINEERING STEP (ONE, evidence-based)

**Accumulate a genuine multi-session 1-minute history and wire `autonomous_momentum`'s live decision path (scheduler's `_generate_validate_signals` + `SignalOptimizer`) into the now-fixed `BacktestEngine`, then run a strict causal, out-of-sample replay over ≥ multiple weeks before making any profitability judgement.**

Concretely: (1) persist daily 1-min NSE bars for both symbols daily (extend `_merge_intraday_into_cache` to keep historical 1-min sessions, not overwrite), and (2) add an `autonomous_momentum` builder to `packages/strategy/candidates.py` (or an engine adapter) that calls the same `classify_regime`+`optimize` functions. Until ≥ several hundred genuine intraday accepted signals accumulate out-of-sample, **no Sharpe/win-rate/profitability claim may be made** for `autonomous_momentum`.

---

## APPENDIX — FILES TOUCHED (this task)
- `reports/AUTONOMOUS_MOMENTUM_HISTORICAL_REPLAY_2026-09-04.md` (this report)
- `packages/backtesting/report.py` — added `BacktestReport` + `compute_metrics` (fixes `advanced.py` ImportError)
- `packages/backtesting/advanced.py` — repaired to real engine API (`BacktestConfig`, async `engine.run`, `.timestamp.date()`), verified executable
- Replay scripts (analysis aids, in `/tmp/opencode/`): `replay_autonomous.py`, `replay2_autonomous.py`, `autonomous_replay2_results.json`

**No strategy logic, thresholds, regime rules, confidence, optimizer, risk, or execution behavior was modified. No live trading. Paper mode unchanged.**
