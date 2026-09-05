# STRATEGY RESEARCH TOURNAMENT — SEPTEMBER 2026

**Date:** 2026-09-05 (reporting on September 2026 data collected through 2026-09-04)
**Scope:** Regime-frequency correction → 5 candidate strategies → fair tournament vs `autonomous_momentum` baseline
**Hard constraints honored:** No live trading. No tuning-to-test. No fabrication. No claim of edge without evidence.

---

## 1. REGIME-FREQUENCY CORRECTION (Phase 1)

### The bug
`RegimeObserver.classify` annualised per-bar volatility with a **hard-coded `sqrt(252)`** — i.e. it assumed **daily** bars. When fed **1-minute** returns, per-bar sigma was scaled by `sqrt(252)` instead of `sqrt(252 × bars_per_day)`, producing a massively understated "annualised" volatility. Every intraday bar therefore fell into the ultra-low-vol bucket and was almost always classified **`sideways`**:

| Input | Before (daily assumption) | After (frequency-correct) |
|---|---|---|
| RELIANCE 360× 1-min (09-04) | `sideways` 339 · `high_vol` 3 · `unknown` 4 | `high_volatility` 328 · `mean_reverting` 28 · `unknown` 4 |
| TCS 360× 1-min (09-04) | `sideways` 339 (dominant) | `high_volatility` 291 · `mean_reverting` 71 · `unknown` 4 |

This single distortion was the dominant reason `autonomous_momentum` (a `trend_following` strategy, compatible only with `trending`/`breakout`/`low_volatility`) was suppressed across the entire intraday session.

### The fix
Added a `periods_per_day` parameter to `RegimeObserver` and correct annualization:

    annualized_vol = std_return × sqrt(252 × periods_per_day)

| Bar frequency | periods_per_day | multiplier |
|---|---|---|
| 1-minute | 360 | ~301.2 |
| 5-minute | 72 | ~134.7 |
| 15-minute | 24 | ~77.7 |
| daily | 1 | ~15.9 (legacy, unchanged) |

- Default stays `periods_per_day=1` → **backward compatible** (existing daily callers unaffected; verified).
- Central mapping in `packages/analytics/frequency.py` so all consumers scale identically.
- The vol/mean **ratio** thresholds (`abs(mean) > k×std`) are scale-free and unchanged.

### Effect on `autonomous_momentum`
Rerun of the documented causal replay with the fixed observer:

| Symbol | momentum>0 candidates | accepted | disposition of accepted |
|---|---|---|---|
| RELIANCE.NS | 168 | 7 | all in `unknown` regime (first ≤21 bars) |
| TCS.NS | 149 | 4 | all in `unknown` regime |

The intraday regime is now honestly `high_volatility`/`mean_reverting`, so the trend-following gate correctly stands aside **for the right reason**: high-vol, choppy single session is **not** trend-following terrain. The strategy still only ever "accepts" during the `unknown` (insufficient-history) regime — a 0 genuine `trending`/`breakout` acceptance remains.

---

## 2. HISTORICAL DATASET

| Asset | Bars | Composition |
|---|---|---|
| RELIANCE.NS | 376 | 16 daily bars (2026-08-03→08-24) + 360× 1-min (2026-09-04 09:15→15:14 IST) |
| TCS.NS | 382 | 22 daily bars (2026-07-27→08-25) + 360× 1-min (2026-09-04) |

- Source: `data/cache/parquet/{RELIANCE_NS,TCS_NS}.parquet` (only historical data present).
- **Only one intraday session exists**; all earlier dates are daily-only.
- No 5-min / 15-min historical data exists → multi-timeframe (5m) evaluation is not possible on this corpus (see §7, Semifinal-5).

---

## 3. STRATEGY CANDIDATES (Phase 3)

| ID | Class | Hypothesis | Signals |
|---|---|---|---|
| A | `TrendFollowingA` | Trends persist; follow cross of regime-confirmed EMA | EMA20/50 + ADX(14)≥20 + ATR>0 + vol_ratio≥1.0 |
| B | `MomentumB` | Intraday momentum persists briefly | RSI(14) zone + MACD-hist sign + ROC(5) sign |
| C | `BreakoutC` | Breakouts with volume + HTF trend confirm | Donchian(20) high + ATR floor + vol_ratio≥1.1 + EMA50 slope |
| D | `MeanReversionD` | Washouts revert to fair value | BB(20,2) z≤-2 + RSI<30 + price<VWAP + ATR ceiling |
| E | `MultiFactorE` | Coherent evidence across factors beats any one | trend+momentum+volatility+volume+regime composite, act at |score|≥2 |
| (base) | `AutonomousMomentumBaseline` | **unchanged** `autonomous_momentum` decision path (reconstructed from audit doc; no `.py` exists in repo) | momentum(5)>0 while flat; confidence=0.60+min(mom,0.30); trend_following regime gate |

## 4. INDICATORS / FEATURES AND JUSTIFICATION (Phase 4 — anti-overfitting)

All features are **causal** (rolling/EWM only up to bar T) and computed once in `packages/research/features.py`:

| Feature | Used by | Economic rationale |
|---|---|---|
| EMA(20), EMA(50) | A, E | trend direction / momentum of mean |
| ADX(14) | A | trend *structure* (filters chop) |
| ATR% | A, C, D | volatility regime / ATR-scaled filters |
| vol_ratio | A, C, E | volume confirmation of price move |
| RSI(14) | B, D | overbought/oversold zones |
| MACD histogram | B | momentum acceleration |
| ROC(5)/(10) | B, E | raw momentum/rate-of-change |
| Donchian(20) | C | breakout channel |
| Bollinger z (BB) | D, E | distance from mean / volatility |
| VWAP | D | intraday fair value anchor |
| `regime_signal` | E | frequency-aware regime factor |

- **No 20+ indicator stacks.** A uses 5, B 3, C 4, D 4, E 5 — all economically justified.
- **No look-ahead**: `execute()` fills at **next-bar close** (`position_exec = target.shift(1)`), proven by `tests/unit/test_research.py::test_execution_is_causal_no_lookahead`. Fills on the crashing bar are paid (test asserts the loss is realised).
- **No arbitary threshold floods**; parameters are few and documented per class.

## 5. EXACT STRATEGY RULES (Phase 5)

**A — Trend:** LONG if `EMA20>EMA50` AND `ADX≥20` AND `ATR%>0` AND `vol_ratio≥1`. FLAT if `EMA20≤EMA50` OR `ADX<18`.

**B — Momentum:** LONG if `RSI ∈ (50,70)` AND `MACD-hist>0` AND `ROC5>0`. SHORT if `RSI ∈ (30,50)` AND `MACD-hist<0` AND `ROC5<0`. FLAT on any factor flipping.

**C — Breakout:** LONG if `close>Donchian20_high` AND `ATR%>0.5%` AND `vol_ratio≥1.1` AND `EMA50 slope>0`. FLAT if `close<Donchian mid` OR slope≤0.

**D — Mean reversion:** LONG if `BB_z≤-2` AND `RSI<30` AND `price<VWAP` AND `ATR%<2%`. FLAT if `BB_z≥0` OR `RSI>50`.

**E — Multi-factor:** factors: trend(±1), momentum(±1), volatility(±1), volume(±1), regime(±1). Composite = sum. LONG if ≥+2; SHORT if ≤-2; else FLAT.

**Baseline (`autonomous_momentum`):** as documented in §1 — momentum(5)>0 while flat → LONG; exit when momentum<0; regime-gate (trend_following-compatible).

## 6. EXECUTION / COST MODEL (fairness guarantee — Phase 2)

Every strategy runs through exactly the same hypothetical execution:

- Signal decided at bar T close → **filled at bar T+1 close** (no same-bar look-ahead).
- Position is a fraction of equity in `{-1,0,1}`; on each unit of turnover we pay `slippage (0.001) + commission (0.0005)` = **0.15% per unit changed** (round-trip ~0.30%).
- Costs scale with **actual notional traded**, so cost per strategy differs only by its own turnover — verified by unit test (`test_costs_turnover_proportional`).
- No candidate receives a different slippage, commission, fill rule, or sample.

---

## 7. TOURNAMENT RESULTS

### 7a. Intraday (Sep-4 session; 360 bars/symbol) — in-sample full-run

| Strategy | Sym | Sig | Tr | Win% | AvgT% | MedT% | Gross% | **Net%** | PF | Exp% | DD% | Sharpe | Hold | Turn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A Trend | REL | 101 | 4 | 25 | +0.147 | −0.056 | +0.61 | **−0.44** | 3.7 | +0.15 | −1.6 | −8.1 | 24.8 | .019 |
| A Trend | TCS | 36 | 1 | 0 | −0.250 | −0.250 | −0.25 | **−0.55** | 0.0 | −0.25 | −0.6 | −33.0 | 36.0 | .006 |
| B Momentum | REL | 153 | 54 | 50 | +0.010 | +0.004 | −0.28 | **−15.20** | 1.37 | +0.01 | −15.2 | −177 | 2.8 | .300 |
| B Momentum | TCS | 129 | 48 | 43.8 | −0.011 | −0.004 | −0.80 | **−13.99** | 0.60 | −0.01 | −14.0 | −177 | 2.6 | .264 |
| C Breakout | REL | 0 | 0 | — | — | — | 0 | **0.00** | — | 0 | 0 | — | — | 0 |
| C Breakout | TCS | 0 | 0 | — | — | — | 0 | **0.00** | — | 0 | 0 | — | — | 0 |
| D MeanRev | REL | 9 | 2 | 100 | +0.117 | +0.117 | +0.31 | **−0.29** | ∞ | +0.12 | −0.3 | −13.2 | 4.5 | .011 |
| D MeanRev | TCS | 64 | 6 | 83.3 | +0.041 | +0.071 | +0.46 | **−1.34** | 2.1 | +0.04 | −1.4 | −35.8 | 10.7 | .033 |
| E MultiFact | REL | 212 | 59 | 35.6 | −0.002 | −0.007 | +0.08 | **−16.04** | 0.95 | 0.00 | −16.1 | −175 | 3.6 | .325 |
| E MultiFact | TCS | 231 | 34 | 38.2 | −0.016 | −0.006 | −0.08 | **−9.78** | 0.58 | −0.02 | −9.9 | −125 | 6.8 | .189 |
| AM Baseline | REL | 3 | 2 | 0 | −0.140 | −0.140 | −0.46 | **−1.06** | 0 | −0.14 | −1.1 | −33 | 1.5 | .011 |
| AM Baseline | TCS | 5 | 2 | 0 | −0.260 | −0.260 | −0.57 | **−1.17** | 0 | −0.26 | −1.2 | −35 | 2.5 | .011 |

**Key reads:**
- **B and E churn** (54/59, 34/48 trades; turnover .19–.33/bar). Zero-cost B ≈ −0.3%/−0.8% (gross), E ≈ 0%/0%; at realistic costs they become −14 to −16%. **They are unviable intraday after costs.**
- **A** has positive gross/PF on RELIANCE but only 4 trades and negative net; **C** never triggers (donchian+volume+trend never aligned on this session); **D** shows positive win-rate/expec on both symbols but only 2–6 trades and negative net after costs.
- **Baseline** traded only the `unknown`-regime early-session bars — 2 trades/symbol, all losers.

### 7b. Daily bars (Aug; 16/22 bars) — illustrative only (not a valid intraday claim)

| Strategy | REL Tr | REL Net% | TCS Tr | TCS Net% |
|---|---|---|---|---|
| A Trend | 0 | 0.00 | 1 | −3.46 |
| B Momentum | 0 | 0.00 | 1 | +0.56 |
| C Breakout | 0 | 0.00 | 0 | 0.00 |
| D MeanRev | 0 | 0.00 | 0 | 0.00 |
| E MultiFact | 2 | −0.65 | 1 | −3.42 |
| AM Baseline | 2 | −1.69 | 3 | −4.96 |

Daily sample is 1–3 trades per cell — **no statistic is meaningful here**.

### 7c. IN-SAMPLE vs OUT-OF-SAMPLE (walk-forward)

Chronological walk-forward, 3 OOS windows per symbol (360 bars → train anchor 90 → OOS 90/90/90; **never shuffled**). All results are single-session.

| Strategy | Total OOS net% (RELI+TCS) | OOS trades | windows negative (of 6) | any positive OOS window |
|---|---|---|---|---|
| A Trend | −1.60 | 4 | 6/6 | NO |
| B Momentum | −24.92 | 82 | 6/6 | NO |
| C Breakout | 0.00 | 0 | 6/6∗ | NO |
| D MeanRev | −1.31 | 7 | 6/6 | NO |
| E MultiFact | −22.92 | 75 | 6/6 | NO |
| AM Baseline | 0.00 | 0 | 6/6∗ | NO |

\* zero-trade windows are trivially "not positive."

**No candidate produced a single positive OOS window.** This is the tournament's central result: on the only usable sample, **the OOS evidence is uniformly negative** (or empty).

---

## 8. MONTE CARLO (Phase 10 — actual trade-return distribution)

Resampling with replacement of each candidate's observed trade P&L distribution (5000 sims, seed 7; per symbol).

| Strategy | Sym | Trades | Status | probLoss | meanFinal | VaR95 | CVaR95 | max-streak p95 |
|---|---|---|---|---|---|---|---|---|
| A Trend | REL/TCS | 4/1 | **INSUFFICIENT SAMPLE** | — | — | — | — | — |
| B Momentum | REL | 54 | OK | 0.28 | 1.005 | 0.993 | 0.990 | 7.0 |
| B Momentum | TCS | 48 | OK | 0.91 | 0.995 | 0.988 | 0.986 | 9.0 |
| C Breakout | REL/TCS | 0/0 | **INSUFFICIENT SAMPLE** | — | — | — | — | — |
| D MeanRev | REL/TCS | 2/6 | **INSUFFICIENT SAMPLE** | — | — | — | — | — |
| E MultiFact | REL | 59 | OK | 0.58 | 0.999 | 0.982 | 0.979 | 9.0 |
| E MultiFact | TCS | 34 | OK | 0.88 | 0.995 | 0.987 | 0.986 | 8.0 |
| AM Baseline | REL/TCS | 2/2 | **INSUFFICIENT SAMPLE** | — | — | — | — | — |

**INSUFFICIENT SAMPLE** is explicitly marked wherever n<8. Where MC runs (B/E), results are not attractive: RELIANCE B sits at 28% loss probability but TCS B and both E runs sit at 58–91% loss probability with tail CVaR ≈ −1 to −2%.

## 9. COST / SLIPPAGE STRESS (Phase 9 — RELIANCE intraday)

| Strategy | BASE (0.1%/0.05%) | +COST (0.1%/0.2%) | +SLIP (0.3%/0.05%) | HIGHER BOTH | Verdict |
|---|---|---|---|---|---|
| A Trend | −0.44 | −1.48 | −1.83 | −2.86 | **fragile** |
| B Momentum | −15.20 | −27.91 | −31.71 | −41.97 | **fragile** |
| C Breakout | 0.00 | 0.00 | 0.00 | 0.00 | N/A (no trades) |
| D MeanRev | −0.29 | −0.89 | −1.09 | −1.68 | **fragile** |
| E MultiFact | −16.04 | −29.59 | −33.60 | −44.33 | **fragile** |
| AM Baseline | −1.06 | −1.65 | −1.85 | −2.44 | **fragile** |

Every candidate that trades is **fragile** — it degrades further (never improves) under modestly higher costs. B/E collapse to −28/−44% (high-turnover rules are cost-saturated).

## 10. REGIME ROBUSTNESS (Phase 8 — intraday, RELIANCE.NS bars)

| Strategy | high_vol (312b) | mean_reverting (28b) | unknown (20b) |
|---|---|---|---|
| A Trend | 4tr / −0.54% | 1tr / −0.05% | 1tr / −0.09% |
| B Momentum | 49tr / −13.96% | 5tr / −1.38% | 2tr / −0.56% |
| C Breakout | 0tr | 0tr | 0tr |
| D MeanRev | 2tr / −0.29% | 0tr | 0tr |
| E MultiFact | 54tr / −14.70% | 5tr / −1.27% | 1tr / −0.37% |
| AM Baseline | 0tr / 0% | 0tr / 0% | 2tr / −1.06% |

Regime robustness is essentially **untestable**: the only intraday session is one `high_volatility` day. `autonomous_momentum` only acts in `unknown` (first 21 bars) because no `trending`/`breakout` regime exists in the sample. **No strategy shows a positive regime-slice.**

## 11. PARAMETER ROBUSTNESS (Phase 11 — RELIANCE intraday)

Neighborhoods of 3 reasonable variants per strategy (E.g. EMA 20/21/10; ADX 18/16/20; RSI zones 70/75/70; Donchian 20/20/10; threshold 2/3/1.5; momentum 5/3/10):

| Strategy | variants | net mean% | net std | min | max | fraction positive |
|---|---|---|---|---|---|---|
| A Trend | 3 | −0.59 | 0.91 | −1.56 | +0.23 | 0.33 |
| B Momentum | 3 | −15.05 | 0.26 | −15.20 | −14.76 | 0.00 |
| C Breakout | 3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| D MeanRev | 3 | −0.19 | 0.17 | −0.29 | 0.00 | 0.00 |
| E MultiFact | 3 | −14.60 | 2.50 | −16.04 | −11.72 | 0.00 |
| AM Baseline | 3 | −0.84 | 0.41 | −1.09 | −0.37 | 0.00 |

No profitable parameter **region** exists; the lone positive variant (A) is a single point, not a stable neighborhood → **consistent with overfitting, not evidence.**

---

## 12. COMPARISON vs `autonomous_momentum` BASELINE (Phase 12)

Full-run intraday (both symbols) and walk-forward OOS:

| Strategy | Intraday net REL% | Intraday net TCS% | Walk-fwd OOS net% (sum) | Trades REL/TCS | Aggregate win% | Cost verdict |
|---|---|---|---|---|---|---|
| A Trend | −0.44 | −0.55 | −1.60 | 4/1 | 20 | fragile |
| B Momentum | −15.20 | −13.99 | −24.92 | 54/48 | 47 | fragile |
| C Breakout | 0.00 | 0.00 | 0.00 | 0/0 | — | no trades |
| D MeanRev | −0.29 | −1.34 | −1.31 | 2/6 | 88 | fragile |
| E MultiFactor | −16.04 | −9.78 | −22.92 | 59/34 | 37 | fragile |
| **autonomous_momentum** | **−1.06** | **−1.17** | **0.00** (no OOS trades; acts in `unknown` first ≤21 bars, inside train anchors) | **2/2** | **0** | fragile |

The baseline is **not allowed to "lose because un-optimized"** — it is compared with its documented defaults, and it produces essentially nothing and loses in the `unknown`-regime trades it does take (2 trades/symbol, 0% wins). **No candidate beats the baseline in OOS terms; the baseline does not win either.**

## 13. EXTERNAL STRATEGIES / AlphaLedger (Phase 13)

- **Not integrated.** No external trader strategies or AlphaLedger components were added to the production architecture in this phase.
- Any external idea will only ever be a **RESEARCH HYPOTHESIS**: independently re-implemented, validated on **our own** historical data, never copied as signals, and never back-filled with current/future external information.
- No action taken; recorded for policy.

## 14. STRATEGY SELECTION RULE (Phase 14)

Requirements to select: positive OOS expectancy AND sufficient trade sample AND acceptable drawdown AND stable PF AND robustness across periods/regimes AND low cost-sensitivity AND no leakage.

**Result: NONE satisfy the criteria. DO NOT SELECT A STRATEGY.**

- OOS expectancy: all ≤ 0 (or empty).
- Trade sample: max ~100 (single session) — insufficient.
- Drawdown: B/E −14/−16% in one session on fresh trends.
- PF stability: unstable or undefined.
- Regime robustness: untestable (single high-vol day).
- Cost sensitivity: all fragile.
- **No candidate is promoted, including `autonomous_momentum`.**

## 15. PAPER-TRADING GATE (Phase 15)

No candidate passes the selection rule ⇒ **nothing advances to paper trading.** Paper trading (if ever triggered) will remain strictly separate from optimization; tuning on paper outcomes will not be relabeled as OOS evidence.

---

## 16. LIMITATIONS (honest assessment)

1. **One intraday session (Sep-4) + ~1 month daily** is the entire usable corpus. Any single-day number (win rate, PF, Sharpe) is a *day*, not a *statistic*.
2. **No multi-day 1-minute, 5-minute, or 15-minute history** → intraday walk-forward is single-session; multi-timeframe testing impossible; regime-robustness breakdown is a single high-vol day.
3. **`autonomous_momentum` has no Python source** in the repo; the baseline is a faithful reconstruction from the audit document (not a tuneable original) — kept unchanged.
4. Costs assume close-fill + 1-bar lag; real fills would be worse intraday (impact, partial fills) — already shown fragile under modestly higher costs.
5. Both symbols are hand-picked from the repo cache → selection bias acknowledged, nothing like a survivorship-free universe.
6. Sharpe/Sortino are computed on single-session bars and are near-meaningless (reported for completeness).

## 17. SUFFICIENCY FOR PAPER TRADING

**NOT sufficient.** The evidence does not meet the minimum bar (positive OOS expectancy after realistic costs, demonstrated stability across periods/regimes). The framework is now trustworthy (causal, uniform costs, tested), but the **data** is not.

---

## FINAL CLASSIFICATION

**D — NO STRATEGY DEMONSTRATES AN EDGE** *(with a dominant E driver: the data/validation basis is insufficient for any positive claim).*

Supporting evidence:
- All 5 candidates **and** the `autonomous_momentum` baseline show non-positive net results with negative or empty OOS windows (Phase 7c).
- High-turnover candidates (B, E) are destroyed by realistic costs; low-turnover candidates (A, C, D) have 0–6 trades and cannot support any claim.
- Regime-robustness, walk-forward, Monte Carlo (where it runs) and parameter neighborhoods consistently fail to show a positive, stable region.
- The binding constraint is **data scarcity** (E) — single session + ~1 month daily — not a hidden winner.

**No strategy was selected. Nothing advances to paper trading.**

---

## FILES ADDED / CHANGED (this task)

| File | Change |
|---|---|
| `packages/analytics/regime_observer.py` | Phase-1 frequency fix (added `periods_per_day` + corrected annualization; backward compatible) |
| `packages/analytics/frequency.py` | NEW — bar-frequency → periods-per-day + annualization multiplier lookup |
| `packages/research/__init__.py` | NEW — research framework package |
| `packages/research/features.py` | NEW — causal feature set (EMA/ADX/ATR/RSI/MACD/ROC/Donchian/BB/VWAP/volume) |
| `packages/research/strategy.py` | NEW — `BaseStrategy` interface |
| `packages/research/candidates.py` | NEW — candidates A–E |
| `packages/research/baseline.py` | NEW — `autonomous_momentum` baseline (reconstructed, unchanged logic) |
| `packages/research/execution.py` | NEW — uniform no-look-ahead execution + costs |
| `packages/research/metrics.py` | NEW — full metric suite |
| `packages/research/evaluation.py` | NEW — walk-forward, regime breakdown, MC, cost stress, param neighborhoods |
| `packages/research/driver.py` | NEW — tournament orchestrator |
| `tests/unit/test_research.py` | NEW — causality/cost/frequency/metrics tests (5 passing) |
| `reports/STRATEGY_RESEARCH_TOURNAMENT_2026-09.md` | THIS report |

*Engine and `autonomous_momentum` trading logic unchanged. Existing `test_indicators.py` failures (3) are pre-existing on Python 3.14/pandas 3.0 (NaN comparison in tests), unrelated to this task.*