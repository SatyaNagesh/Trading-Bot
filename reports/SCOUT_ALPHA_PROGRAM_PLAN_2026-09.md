# SCOUT ALPHA PROGRAM — Plan (Information-Driven Alpha Discovery)

**Date:** 2026-09-13
**Status:** Plan only. Sequence of research phases; implementation is gated.

Companion: `reports/QUANTLAB_SCOUT_SPEC_2026-09.md` (binding spec).

---

## 0. Context and motivation

- COMP3 (`COMP3_REVERSAL_BREADTH_DISP`) rejected twice on independent holdsouts
  as **concentration-fragile**. See `reports/COMP3_PROGRAM_CLOSEOUT_2026-09.md`.
- Next program changes the information source while keeping the validation
  discipline identical.

## 1. Phase 1 — Architecture (packages/discovery/)

```
packages/discovery/
  news/                  ingested articles/filings/transcripts as facts
  fundamentals/          change/acceleration features
  macro/                 macro event time-series + event marks
  events/                normalized typed events with strict timestamps
  entity_mapping/        symbol <-> industry <-> exposure tables
  opportunity_scoring/   research (not trading) score
  research_hypotheses/   hypothesis registry + multiple-testing ledger
```

Scout is a research/discovery layer only. No separate trading bot; existing
trading/risk/execution stay isolated.

## 2. Phase 2 — Event taxonomy

Closed set (see spec §4): MACRO, POLICY/GEOPOLITICS, COMPANY. No expansion
without a spec amendment.

## 3. Phase 3 — Entity / exposure mapping

EVENT → INDUSTRY → MECHANISM → EXPOSURE. Quant model computes exposure from
financials; LLM/NLP never outputs direction for the model to use blindly.

## 4. Phase 4 — Fundamental change detection

Change/acceleration features (§6 of spec): growth, margins, ROCE, debt, cash
flow, order book, capacity, estimate revisions, ownership trends.

## 5. Phase 5 — Macro → industry → company model

Transmission chain with fundamental confirmation step before any price
response measurement.

## 6. Phase 6 — Early opportunity score

Research scoring (§8): outputs EARLY OPPORTUNITY / RESEARCH ONLY / REJECTED.

## 7. Phase 7 — Historical event study (core)

Forward returns at 1/3/5/10/20d per event type, strict timestamps, no leakage.

## 8. Phase 8 — Under-reaction detection

Abnormal return, volume, relative strength, subsequent earnings confirmation,
post-event drift.

## 9. Phase 9 — Cross-sectional testing

Rank exposed names by exposure/fundamentals/valuation/reaction; test future
cross-sectional returns; no assumption the best-looking name wins.

## 10. Phase 10 — AI/NLP research

Structured fact extraction only (source, timestamp, entity, event type,
confidence, evidence). No generated text as trading signal.

## 11. Phase 11 — Alpha validation

Standard QuantLab battery: DEVELOPMENT → VALIDATION → OOS → COSTS →
WALK-FORWARD → NEW HOLDOUT. No special treatment for AI ideas.

## 12. Phase 12 — Multiple-testing control

Hypothesis registry: every `event × exposure × horizon` cell counted; FDR /
permutation controls; no winner-only reporting.

## 13. Phase 13 — New holdout

Untouched corpus, disjoint from all previous universes, locked (manifest +
sha256 + eligible set) before evaluation.

## 14. Phase 14 — Surviving discoveries become strategies

Only a replicated, validated finding builds a simple tradeable wrapper.

## 15. Phase 15 — Paper-trading gate

All conditions of spec §16 must hold. Scout-alone never trades.

## 16. Immediate gate (this commit)

Deliverables already produced at this gate:
1. `reports/QUANTLAB_SCOUT_SPEC_2026-09.md`
2. `reports/SCOUT_ALPHA_PROGRAM_PLAN_2026-09.md`
3. `packages/discovery/` — data model / schemas / interfaces (skeleton)

## 17. Not started yet (next gate review)

Actual ingestion, NLP, event detection, and backtests begin only after review
of this spec + plan + schemas.