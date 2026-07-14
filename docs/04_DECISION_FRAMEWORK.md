# QuantLab AI — Decision Framework

> **How We Make Choices**  
> Version 1.0 | Last Updated: July 2026

---

## Decision Philosophy

Every decision in QuantLab AI shall be:
1. **Explicit** — Stated clearly, not assumed
2. **Rational** — Based on evidence, not intuition
3. **Documented** — Recorded with rationale
4. **Reversible** — Designed to be changeable
5. **Timely** — Made when needed, not delayed

---

## The Five Essential Questions

Before any significant decision, ask:

### 1. What problem are we solving?
- What is the specific, measurable issue?
- Who is affected?
- What happens if we don't solve it?

### 2. What are our options?
- List at least 3 alternatives
- Include "do nothing" as an option
- What are the trade-offs of each?

### 3. What does the evidence say?
- What data supports each option?
- What assumptions are we making?
- How confident are we in the evidence?

### 4. What are the consequences?
- What are the immediate effects?
- What are the second-order effects?
- What happens in worst-case scenarios?

### 5. How do we measure success?
- What metrics will we use?
- What timeline for evaluation?
- What triggers a reversal?

---

## The Three Gates

Every decision passes through three gates:

### Gate 1: Constitutional Check
Does this decision violate any of the 12 Laws?
- If yes: Stop. Find another path.
- If unclear: Seek clarification before proceeding.

### Gate 2: Evidence Check
Do we have sufficient evidence to make this decision?
- High confidence: Proceed
- Medium confidence: Proceed with monitoring
- Low confidence: Gather more evidence first

### Gate 3: Risk Check
What is the worst-case outcome?
- Acceptable: Proceed
- Mitigable: Proceed with safeguards
- Unacceptable: Find another path

---

## Decision Categories

### Type A — Irreversible Decisions
Examples: Database schema changes, API contract changes, security architecture
- Require full documentation
- Require 24-hour review period
- Require rollback plan
- Require stakeholder sign-off

### Type B — Significant Reversible Decisions
Examples: New service, library choice, algorithm selection
- Require documentation
- Require peer review
- Require success metrics

### Type C — Routine Decisions
Examples: Bug fix approach, test strategy, minor refactoring
- Documented in PR description
- Standard review process

### Type D — Trivial Decisions
Examples: Variable naming, comment style, formatting
- No documentation needed
- Follow established conventions

---

## Decision Template

```markdown
# Decision: [Title]

## Status
[Proposed | Accepted | Deprecated | Rejected]

## Context
[What prompted this decision?]

## Options Considered
1. Option A — [pros/cons]
2. Option B — [pros/cons]
3. Option C — [pros/cons]

## Decision
[What we chose and why]

## Consequences
[What this means for the project]

## Metrics
[How we measure success/failure]
```

---

## Trade-Off Matrix

When choosing between options, evaluate on:

| Criteria | Weight (1-5) | Option A | Option B | Option C |
|----------|-------------|----------|----------|----------|
| Development time | | | | |
| Runtime performance | | | | |
| Maintenance burden | | | | |
| Scalability | | | | |
| Testability | | | | |
| Cost | | | | |
| Learning curve | | | | |

---

## Escalation Path

If consensus cannot be reached:
1. **Standard** — Discuss with team, 48-hour decision window
2. **Fast** — Project lead decides, documented immediately
3. **Emergency** — On-call decides, documented within 24 hours

---

## Anti-Patterns

Decisions should NOT be based on:
- "We've always done it this way"
- "Everyone else is doing it"
- "It worked for [big company]"
- "It's faster to do it wrong and fix it later"
- "We'll add it later" (architectural decisions only)
