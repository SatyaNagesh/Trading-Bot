# Signal Journal — Candidate Observability Step (2026-09-04)

**Goal:** Determine WHY `autonomous_momentum` produces zero accepted signals, WITHOUT changing
any strategy logic. Deliverable: a durable, immutable, queryable candidate-signal journal that
records EVERY decision (accepted / suppressed / rejected) with the exact inputs to the decision,
plus out-of-sample forward evaluation of suppressed candidates.

**Status: DEPLOYED** in the running PAPER runtime (systemd PID 637745). All tests green.

---

## A. What was built

A best-effort observability layer grafted onto the EXISTING decision path. It observes, never
decides. Strategy logic, thresholds, regime rules, filters, and confidence requirements are
untouched — verified by dedicated behavior-unchanged tests.

| Artifact | File | Purpose |
|---|---|---|
| Journal repository | `packages/analytics/signal_journal.py` | Append-only JSONL `SignalJournal`, bounded retention, immutable records, `funnel_stats()`, `verify_immutable()`, `evaluate_forward()` |
| Scheduler hook | `packages/core/scheduler.py` | `_journal_candidate()` called after each optimizer decision |
| Config | `packages/core/config.py` | `SIGNAL_JOURNAL_MAX_RECORDS=50_000`, `SIGNAL_JOURNAL_RETENTION_DAYS=30` |
| API | `apps/api/main.py` | `GET /api/v1/signals/journal` and `.../stats` |
| CLI | `tools/signal_journal_query.py` | `--stats --top-reasons --rows --forward` filters |
| Tests | `tests/phase10_signal_journal_tests.py` | 13 focused tests |

## B. Decision-path instrumentation (what each record contains)

In `_generate_validate_signals`, immediately AFTER `optimizer.optimize(...)` returns, we append one
immutable record with the byte-exact inputs that produced the decision:

- `symbol`, `price`, `last_close`, `bars` count, `last_bar_ts`, `last_bar_close`
- `indicator_input`: `last_bar_count`, `regime_bars_window=60`
- `signal`: `direction`, `confidence`, `strategy_id=autonomous_momentum`
- `regime` (the same dict the optimizer used)
- `optimizer`: `decision`, `reason`, `calibration_applied`, `optimizer_confidence`
- `decision` / `reason` (accepted or suppressed + canonical reason)
- `strategy_status`, `strategy_session` (UTC date), `mode`, `timeframe=1m`, `data_ts`

The hook reads `result` and inputs already in local scope — it performs **no additional
computation that could influence the decision**, and is wrapped in try/except so a journal failure
can never break the trading loop.

## C. Guarantees

- **Immutable:** unique `record_id` per write; reader returns deep copies; canonical (sorted-key)
  serialization; `verify_immutable()` digest check.
- **Every candidate captured:** accepted AND suppressed both journaled — nothing is dropped.
- **Bounded retention:** `max_records` compaction + optional `retention_days`; atomic tmp+`os.replace`.
- **Forward eval, no look-ahead:** `evaluate_forward(record, bars, horizons, txn_cost)` uses ONLY
  bars strictly after `data_ts`. Diagnostics only — never converts suppressed→trades, never mutates
  the original record.

## D. Test results

- `tests/phase10_signal_journal_tests.py`: **13/13 PASS**
  (A accepted, B suppressed, C reasons, D tz-aware, E immutable, F no-loss, G mode, H bounded
  retention, H2 retention_days, I behavior-unchanged, J risk-guard-unchanged, K funnel_stats,
  L forward-eval)
- Phase 9 + Phase 8 regression: **67 passed / 0 failed**
- `tests/runtime_validation.py`: **16/16 PASS** (when awaited within a single event loop; the file's
  standalone `__main__` mis-reports 16 FAIL due to a pre-existing nested `asyncio.run` bug — not in
  this change set)
- All modified files `py_compile` clean; API app imports with both new routes registered.

## E. Deployment (live PAPER runtime)

- Restarted `quantlab-runtime.service` → **PID 637745** (required: Python module cache is stale on
  hot edit).
- Verified live: mode=`paper`, kill_switch=false, no breaches, `autonomous_momentum`=`active`,
  scheduler `running`, `GET /api/v1/signals/journal/stats` returns the full schema.
- Journal file is created lazily on first write (NSE market closed at deploy time), so stats read
  `total_candidates: 0` until the next session (Mon 2026-09-07; 2026-09-14 is an NSE holiday).

## F. Defects introduced & fixed during this step

1. Retention compaction dropped the trailing newline on `_canonical_line`, concatenating records
   and corrupting the JSONL. Fixed to write `+ "\n"`.
2. `record()` now uses canonical (sorted-key) lines consistently across append and compaction so
   `verify_immutable()` holds.
3. A flawed test called a non-existent `SafetyGuard.assert_paper()`; rewrote to use the real
   `assert_paper_trading()` and to verify LIVE hard-block + module-level `assert_paper_trading_safe`.

## G. Strategy-unchanged confirmation

`SignalOptimizer` (the canonical decision logic) was **read-only** this session. The only scheduler
change is the post-decision append. Tests `I_strategy_behavior_unchanged` and
`J_risk_guard_unchanged` pass, and the live runtime still reports `autonomous_momentum`=active.

## Next step (ONE, evidence-based)

Let the instrumented runtime collect a full week of genuine candidates in PAPER mode (next valid
trading session 2026-09-07), then run the CLI/API funnel analysis to answer the A–F funnel chain:
**How many raw candidates → accepted → executed → profitable? and for EVERY rejected candidate,
which suppression reason dominates (regime_incompatible_ranging / low_confidence /
invalid_direction / strategy_degraded)?** First do NOT re-tune after a handful of records — gather
≥ a week (≥ several hundred candidates) before any threshold change. Rank the top suppression reason
by frequency; that single reason is the primary lever explaining zero accepted signals.
