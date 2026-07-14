# RFC-002: Engine Count & Organization

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Doc 35 (Operating System) states "17 Engines" but the mapping reveals:

| Claimed Engine | Document | Reality |
|---------------|----------|---------|
| Optimization Engine | 33_BACKTEST | Section within Backtest, not separate doc |
| Validation Engine | 30_RESEARCH | Section within Research, not separate doc |
| Backtest Engine | 33_BACKTEST | Correct |
| Research Engine | 30_RESEARCH | Correct |

Additionally, Execution Engine has no doc (see RFC-001).

## Option A: Accept 15 Distinct Engines

Merge Optimization into Backtest, Validation into Research. Update doc 35.

**Pro**: Fewer docs to maintain, simpler architecture, avoids artificial splits.

**Con**: Engines with shared docs could grow beyond their parent and need splitting later.

## Option B: Create Separate Docs for Optimization & Validation

Create:
- `docs/36_EXECUTION_ENGINE_SPEC.md` (needed regardless — see RFC-001)
- `docs/37_OPTIMIZATION_ENGINE_SPEC.md`
- `docs/38_VALIDATION_ENGINE_SPEC.md`

**Pro**: Each engine has dedicated scope, follows "one spec per engine" pattern.

**Con**: Doc count grows to 38, harder to maintain, Optimization is tightly coupled to Backtest.

## Recommendation

**Option A** — Merge Optimization into Backtest and Validation into Research. This is more honest about the architecture and reduces maintenance burden. If either sub-component later justifies independent status, it can be extracted with minimal disruption.

## Changes Required

| Document | Change |
|----------|--------|
| doc 35 | Update "17 Engines" → "15 Engines" in Section III table |
| doc 33 | Add "Optimization Engine" as named Component with clear section boundary |
| doc 30 | Add "Validation Engine" as named Component with clear section boundary |

## Action

- [ ] Update doc 35 Section III table
- [ ] Add subsection headers in doc 30 and doc 33 for Validation/Optimization
