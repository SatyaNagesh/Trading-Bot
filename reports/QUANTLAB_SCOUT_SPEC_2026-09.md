# QUANTLAB SCOUT — Specification (Information-Driven Alpha Discovery Layer)

**Date:** 2026-09-13
**Status:** Specification / initial schemas only. Research-scaffolding gate —
the Scout is NOT built yet and nothing here creates a strategy or a trade.

Companion: `reports/SCOUT_ALPHA_PROGRAM_PLAN_2026-09.md`.

---

## 1. Purpose

COMP3 (resolution, breadth/dispersion, reversal) scored positively in
development but was rejected twice on independent holdouts because its edge was
**concentration-fragile** — the P&L depends on a handful of names. The next
program changes the *information source*, not the validation discipline.

QuantLab Scout is a **discovery engine**, not an execution engine. It exists to
turn **material information** (fundamentals, earnings, corporate events,
industry change, macro/policy, geopolitics, news/filings) into **research
hypotheses whose legacy returns can be measured and cross-validated** under the
same dev → validation → OOS → costs → walk-forward → holdout rules as every
other QuantLab alpha.

The goal is NOT to predict news sentiment. The goal is:

> **DETECT MATERIAL INFORMATION → IDENTIFY EXPOSED COMPANIES → MEASURE MARKET
> REPRICING → TEST WHETHER THE EFFECT IS TRADABLE.**

## 2. Non-goals (hard rules)

- No COMP3 revival; no technical-indicator soup; no copying external traders.
- No LLM or news sentiment may directly trigger trades or issue BUY/SELL.
  LLM/NLP output is **extracted facts**; only numeric code validates a thesis.
- No AlphaLedger integration, no live trading, no paper trading from this layer.
- No "optimize until P&L positive"; multiple-testing controls apply.
- No hundreds of event classes; the taxonomy is small and controlled.

## 3. Architecture

```
SCOUT (research/discovery)                     EXISTING SYSTEMS (separate)
  news/ fundamentals/ macro/ events/              trading engine
  entity_mapping/ opportunity_scoring/            risk engine
  research_hypotheses/                            paper runtime
    |
    v
RESEARCH HYPOTHESIS (registered, costed, counted)
    |
    v
ALPHA TEST (dev split; cross-sectional, FDR-controlled)
    |
    v
OOS VALIDATION (validation split, report-only)
    |
    v
COSTS + WALK-FORWARD + TAIL (same battery as COMP3)
    |
    v
NEW HOLDOUT (disjoint, locked before evaluation)
    |
    v
PAPER-TRADING GATE (Phase 15)  -- only surviving discoveries qualify
```

The Scout is an event/data pipeline owned by `packages/discovery/`. It emits
**research objects** (facts + mechanisms + exposure candidates), never orders.

## 4. Event taxonomy (controlled, closed set)

Categories and exemplar events. New classes require a spec amendment
(pre-registration discipline).

### MACRO
- inflation prints, interest-rate changes, RBI policy actions
- FX shocks, crude/commodity shocks, bond-yield moves
- government spending, credit conditions

### POLICY / GEOPOLITICS
- tariffs, trade agreements, import/export restrictions
- government incentives, production-linked incentives, infrastructure programs
- sanctions, geopolitical disruptions

### COMPANY
- earnings surprise, revenue acceleration, margin expansion
- order wins, contract announcements, capacity expansion
- acquisitions, debt reduction, management guidance changes, product launches

## 5. Entity / exposure mapping (the critical step)

An event becomes:

```
EVENT → INDUSTRY → ECONOMIC MECHANISM → COMPANY EXPOSURE
```

Example research object:

```text
event:          oil price decline
event_ts:       <strict UTC timestamp of the information release>
mechanism:      lower input/transport cost -> margin expansion for importers;
                revenue/realisation risk for upstream producers
exposure:       beneficiaries {A, B, C}, losers {D}   (from a QUANT MODEL, not a model
                outputting BUY/SELL)
evidence:       revenue exposure, input-cost share, historical sensitivity
confidence:     0-1
```

Classification of an article as "positive/negative" is NOT the output. The
**mechanism** and the **quantitative exposure** are the outputs.

## 6. Fundamental change detection (change, not level)

Build CHANGE features (acceleration / improvement), not absolute quality:

- revenue growth acceleration, EPS growth acceleration, margin expansion
- ROCE improvement, debt reduction, cash-flow improvement
- order-book growth, capacity expansion, (where reliable) estimate revisions
- institutional ownership trend (where valid)

Working hypothesis: **improving fundamentals + catalyst + under-reaction**,
not simply low valuation.

## 7. Macro → industry → company model

Structured transmission chain:

```
MACRO EVENT → INDUSTRIES AFFECTED → POSITIVE/NEGATIVE TRANSMISSION
           → COMPANIES WITH EXPOSURE → FUNDAMENTAL CONFIRMATION → PRICE RESPONSE
```

LLM/NLP may extract: event, affected entities, direction, mechanism,
confidence, supporting evidence (source + timestamp + reference). Quant code
independently validates the thesis.

## 8. Early-opportunity score (RESEARCH score, not a trading score)

Components (each numeric, each pre-registered weight):
fundamental_improvement, event_strength, industry_tailwind, macro_alignment,
abnormal_market_reaction, relative_strength, valuation_context, liquidity,
already_priced_in_penalty.

Output buckets: `EARLY OPPORTUNITY` | `RESEARCH ONLY` | `REJECTED`.
Never `BUY`.

## 9. Historical event study (the core deliverable)

For every event type, measure forward returns of exposed companies at
**1d / 3d / 5d / 10d / 20d**, with strict event timestamps (information
available only up to `t`), no future data.

## 10. Under-reaction detection

Explicitly investigate: EVENT OCCURS → COMPANY REACTION → HAS THE MARKET FULLY
PRICED IT? Measurements: abnormal return, volume response, relative strength,
subsequent earnings confirmation, post-event drift. This is the channel that
addresses "unknown company that later booms".

## 11. Cross-sectional testing

For multi-company events, rank exposed companies by exposure strength,
fundamental improvement, valuation, and market reaction, then test future
cross-sectional returns. Do NOT assume the strongest-looking name wins.

## 12. AI / NLP use (constrained)

NLP is used only where it adds information unavailable from structured price
data: filings, transcripts, official releases, corporate announcements.
Output = structured facts, each retaining source, timestamp, entity, event
type, confidence, and evidence reference. Generated text never becomes the
final signal.

## 13. Validation discipline (identical to prior programs)

Every discovered hypothesis enters the standard QuantLab pipeline:
DEVELOPMENT → VALIDATION → OOS → COSTS → WALK-FORWARD → NEW HOLDOUT → PAPER
GATE. No special treatment for AI/news-derived ideas.

## 14. Multiple-testing control

Every `event × exposure × horizon × metric` cell counts toward the discovery
universe. A pre-registered hypothesis registry and FDR/permutation controls
(already used in QuantLab) apply. No reporting only winners.

## 15. New holdout

A completely untouched holdout, disjoint from all earlier strategy-development
universes, frozen before evaluation, reusing the locked-corpus discipline of
COMP3 (manifest + sha256 lock + eligible set).

## 16. Paper-trading gate (Phase 15)

A Scout-derived strategy may enter paper trading only if ALL hold: replicated
OOS; event/feature effect replicated; positive net expectancy; realistic cost
positive; sufficient observations; acceptable drawdown; NO concentration
dependence (the COMP3 lesson); temporal robustness; no leakage; independent
holdout confirmation.

## 17. Deliverables of THIS gate

- `reports/QUANTLAB_SCOUT_SPEC_2026-09.md` (this file)
- `reports/SCOUT_ALPHA_PROGRAM_PLAN_2026-09.md`
- `packages/discovery/` initial schemas + interfaces (see below)

Implementation of the pipeline itself is deferred to the next gate.