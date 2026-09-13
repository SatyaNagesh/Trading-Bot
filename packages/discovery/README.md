# QuantLab Scout — packages/discovery

Discovery-layer schemas and interfaces for information-driven alpha research.

**THIS IS NOT A TRADING SYSTEM.** The Scout produces research objects — facts,
mechanisms, exposure candidates, hypotheses, research scores. It produces no
orders and no BUY/SELL outputs.

## Layout

| Directory | Contents |
|---|---|
| `events/` | normalized typed events with strict timestamps + closed taxonomy |
| `news/` | ingested articles / filings / transcripts as provenance-kept facts |
| `fundamentals/` | change/acceleration features (not absolute levels) |
| `macro/` | macro event marks and time series |
| `entity_mapping/` | symbol ↔ industry ↔ economic-mechanism exposure tables |
| `opportunity_scoring/` | RESEARCH score (not a trading score) with pre-registered components |
| `research_hypotheses/` | hypothesis registry + multiple-testing ledger |

## Rules

1. Every extracted fact keeps `source`, `timestamp`, `entity`, `event_type`,
   `confidence`, and an `evidence` reference.
2. LLM/NLP output is always **facts**, never direction for the model; quant
   code independently validates exposure and price response.
3. Event kinds come from a closed taxonomy (`events.taxonomy`); additions
   require a spec amendment.
4. Hypothesis decks count every `event × exposure × horizon` cell against a
   multiple-testing ledger (FDR / permutation controls).
5. Only a discovery that passes the full dev → validation → OOS → costs →
   walk-forward → new holdout → paper gate pipeline may become a strategy.

This gate ships **schemas only**. Ingestion/NLP/backtest implementation is a
later, separately reviewed step.