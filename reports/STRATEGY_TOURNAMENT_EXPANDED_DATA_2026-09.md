# STRATEGY TOURNAMENT — EXPANDED HISTORICAL DATA (SEPTEMBER 2026)

**Date:** 2026-09-05
**Scope:** Re-run of the six-entry tournament from `STRATEGY_RESEARCH_TOURNAMENT_2026-09.md` on the expanded, audited corpus (`HISTORICAL_DATA_AUDIT_2026-09.md`) — 49 NIFTY-50 symbols × 12.7 years of daily bars, split chronologically.
**Hard constraints honored:** No new strategies. No parameter re-tuning. Identical costs, slippage, execution, and evaluation for every entry. TRAIN development only; VALIDATION + FINAL-OOS scored once at the end. FINAL-OOS never touched during development.

---

## 1. Dataset & methodology (unchanged framework, more data)

| | Original tournament | This tournament |
|---|---|---|
| Data | 1 intraday session + 16–22 daily bars (2 symbols) | 151,184 daily bars across 49 NIFTY-50 symbols (2014→2026) |
| Splits | — | TRAIN 2014→2023 · VALIDATION 2023→2025-07 · FINAL-OOS 2025-07→2026-09 |
| Universe | RELIANCE, TCS | full NIFTY-50 (TATAMOTORS excluded — unavailable at source) |
| Strategies | A trend, B momentum, C breakout, D mean-reversion, E multi-factor, + baseline | **identical entries, unmodified** |
| Costs | slippage 0.10% + commission 0.05% per side | identical (`BASE_COST`) |
| PPD | 1 (daily) | 1 |
| MC seed | 7, 5000 sims | 7, 2000 sims |

Evaluation per entry: per-split metrics, pooled OOS statistics (mean, median, win rate, PF, expectancy, CI95 bootstrap), 3-window chronological walk-forward, regime breakdown, cost stress (4 scenarios), parameter-neighborhood robustness, and a rules-based `decision()`.

### `decision()` gates (added for this run — honest, not lenient)
- `pooled OOS trades < 30` → **INSUFFICIENT DATA**
- expectancy ≤ 0 or CI95 lo ≤ 0 → **NO EDGE**
- then robustness gates; any failure → **OVERFIT/FRAGILE**:
  - PF < 1.2, win rate < 40%, parameter-neighborhood positive fraction < 0.5,
  - cost-fragile on > 50% of symbols,
  - regime-positive fraction < 0.5,
  - **outlier-driven** (top 10% of trades > 90% of net profit),
  - **most-recent OOS window negative** (≥ 30 trades, expectancy ≤ 0).
- only if all pass → **PROMISING — MORE DATA**.

## 2. Results (pooled out-of-sample: VALIDATION + FINAL-OOS)

Pooled OOS = all closed-trade net returns from the two held-out windows across all 49 symbols.

| Strategy | OOS Trades | OOS Ret avg/trade | Expectancy | Median | PF | Win Rate | Max DD* | CI95 | Decision |
|---|---|---|---|---|---|---|---|---|---|
| autonomous_momentum_baseline | 1 | +0.31% | +0.31% | +0.31% | ∞ | 100% | 0.0% | — | **INSUFFICIENT DATA** |
| A trend-following | 525 | +2.41% | +2.41% | −0.52% | 2.06 | 43.4% | −15.4% | [1.34, 3.57] | **OVERFIT/FRAGILE** |
| B momentum | 5,820 | −0.35% | −0.35% | −0.44% | 0.69 | 40.6% | −26.2% | [−0.42, −0.28] | **NO EDGE** |
| C breakout | 0 | — | — | — | — | — | 0.0% | — | **INSUFFICIENT DATA** |
| D mean-reversion | 1 | +2.18% | +2.18% | +2.18% | ∞ | 100% | 0.0% | — | **INSUFFICIENT DATA** |
| E multi-factor | 6,625 | −0.36% | −0.36% | −0.58% | 0.70 | 36.8% | −31.6% | [−0.44, −0.29] | **NO EDGE** |

\* Max DD = median per-symbol per-window OOS drawdown (negative = drawdown), from `per_split_metrics`.

**The only way to trade these entries profitably out-of-sample was not to trade at all.** Baseline, C, and D essentially never fire on daily bars over OOS (1, 0, and 1 trades), so their "100% win / PF ∞" is an artifact of sample size, not edge.

## 3. Per-window breakdown — the trend-following story

The single most important result of this tournament is how **A's positive pooled number is a mirage**:

| Window | Trades | Expectancy | Median | Win | PF | CI95 |
|---|---|---|---|---|---|---|
| VALIDATION (2023→2025-07, bull phase) | 349 | +3.74% | −0.26% | 45.6% | 2.80 | [2.21, 5.51] |
| **FINAL-OOS (2025-07→2026-09, most recent)** | 176 | **−0.23%** | −0.98% | 39.2% | **0.91** | [−1.36, 0.99] |

The pooled +2.41% expectancy is driven almost entirely by the right tail during the 2023–2025 equity bull run:
- Typical trade loses money: median **−0.52%**, win rate 43.4%.
- **Top 10% of trades (52 of 525) = 133% of ALL net profit.** The remaining 90% of trades are, in aggregate, breakeven-to-losing.
- A handful of monster single-trade runs (+113%, +113%, +76%, +71%…) on names like TRENT, SHRIRAMFIN, BAJAJ-AUTO, ONGC, BEL, COALINDIA produced the entire edge.
- The most recent 14 months — the period that matters for future deployment — is **negative** (PF 0.91).

This is the canonical signature of a **regime-dependent, right-tail gamble**, not a tradeable edge. Weighted by which period comes last, A fails on both new robustness gates (outlier-driven, most-recent-window-negative).

## 4. Robustness checks

| Strategy | Param-positive frac | Cost-fragile symbols | Regime-positive frac | Regimes |
|---|---|---|---|---|
| A trend-following | 0.69 | 20/49 | 1.00 | high_vol, mean_reverting |
| B momentum | **0.05** | **49/49** | 0.50 | high_vol, mean_reverting |
| C breakout | 0.00 | 0/49 | 0.00 | high_vol, mean_reverting |
| D mean-reversion | 0.01 | 0/49 | 0.50 | high_vol, mean_reverting |
| E multi-factor | **0.09** | **49/49** | 1.00 | high_vol, mean_reverting |
| autonomous_momentum_baseline | 0.01 | 1/49 | 0.00 | high_vol, mean_reverting |

- **B (momentum) and E (multi-factor):** decisive NO EDGE. 5,820 and 6,625 OOS trades respectively, expectancy ≈ −0.35%/trade with the entire 95% CI negative. They are **cost-fragile on all 49 symbols** and their parameter neighborhoods are positive on ≤ 9% of variants — consistently negative, consistently fragile, at real scale.
- **D (mean-reversion)** fires once because its reversal trigger (+5% bollinger-band exit from daily signal) essentially never closes a qualifying round trip on daily data — it remains un-proven rather than disproven.

## 5. Sample-size honesty

| Strategy | Pooled OOS trades | Verdict basis |
|---|---|---|
| baseline | 1 | INSUFFICIENT (cannot label profitable) |
| A | 525 (but edge = 52 tail trades) | OVERFIT/FRAGILE (regime-dependent right tail) |
| B | 5,820 | NO EDGE (statistically clean negative) |
| C | 0 | INSUFFICIENT (never fires) |
| D | 1 | INSUFFICIENT (never fires) |
| E | 6,625 | NO EDGE (statistically clean negative) |

## 6. Conclusion & decision

**Overall tournament grade: D — NO EDGE. Nothing advances; nothing to paper trade.**

The expanded dataset does more than confirm the original verdict — it **hardens** it:
1. **Momentum and multi-factor are now decisively dead** on thousands of out-of-sample trades (negative expectancy, negative CI, cost-fragile everywhere, parameter-fragile). These are the two entries with the most evidence, and the evidence is squarely negative.
2. **Trend-following is not a hidden winner.** Its apparent +2.4%/trade is 133%-concentrated in the top-10% of trades, median trade −0.52%, and **it lost money in the most recent 14 months** (PF 0.91). On data that would matter to forward deployment, it under-performs.
3. **Breakout, mean-reversion, and the baseline** produce effectively zero out-of-sample trades on daily bars — they are un-proven, not profitable, and cannot be deployed without intraday horizons this corpus cannot support.

Consistent with the original tournament, **no strategy demonstrated a sustainable edge under costs**. The expanded corpus's contribution is evidentiary: the negative conclusions for B and E rest on thousands of trades, and the apparent trend-following edge is diagnosed (not merely dismissed) as a bull-phase tail gamble.

**Nothing qualifies for live/paper trading.** If asked to pick the single most honest characterization: the only edge found in the entire expanded corpus is that none of these entries trades profitably out-of-sample when costs are applied honestly.