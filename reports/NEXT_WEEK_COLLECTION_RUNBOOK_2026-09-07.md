# Week-Long Out-of-Sample Signal Collection — Runbook (2026-09-07 → 2026-09-11)

**Purpose:** Collect genuine, unbiased evidence from the UNCHANGED `autonomous_momentum`
strategy across the next valid NSE sessions, via the deployed signal journal.

**HARD RULES (do not break):**
- PAPER_TRADING only. Live trading stays hard-blocked.
- Do NOT change strategy logic, thresholds, confidence, regime rules, optimizer, risk,
  or execution behavior during the whole collection window.
- Do NOT manually intervene in signals, inject/replay/fabricate data, or retune anything.
- The runtime runs under systemd and must stay running across the sessions.

---

## What runs automatically (no action needed)
- systemd `quantlab-runtime.service` (PAPER) runs the scheduler during each NSE session
  (09:15-15:30 IST, weekdays; 2026-09-14 is an NSE holiday — skip).
- Every candidate (accepted AND suppressed) is journaled to `data/signal_journal.jsonl`
  by the scheduler hook, with symbol/price/regime/direction/confidence/decision/reason.
- `GET /api/v1/signals/journal/stats` and `.../journal` are live on port 8000.

## Recommended session schedule (valid NSE trading days)
| Day | Date (2026) | Action |
|---|---|---|
| Mon | 09-07 | run, health-check, record counts |
| Tue | 09-08 | run, health-check, record counts |
| Wed | 09-09 | run, health-check, record counts |
| Thu | 09-10 | run, health-check, record counts |
| Fri | 09-11 | run, health-check, then FINAL report |
| (Mon | 09-14 | NSE HOLIDAY — no session) |

## Per-session observation-only health check
After each session's close, run:

```
systemctl --user status quantlab-runtime.service              # must be active/running
cd /home/satyanagesh/Documents/opencode-discord-bot/work/Trading-Bot
poetry run python tools/signal_journal_week_report.py --health
poetry run python tools/signal_journal_week_report.py        # A..Q (pending until data)
curl -s http://localhost:8000/api/v1/risk/status             # paper mode, kill_switch false
curl -s http://localhost:8000/api/v1/signals/journal/stats   # candidate counts
```

**Health criteria (all must hold; record any deviation):**
- Runtime: `active (running)`, scheduler `running`.
- Mode `paper`, kill_switch `false`, no `breaches` (risk controls active).
- `autonomous_momentum` status `active`.
- Journal writing: `data/signal_journal.jsonl` exists and grows each session.
- No silent loss: the journal record count that day matches the scheduler's
  `signals_generated` for that day (scheduler stats endpoint).
- Checkpoint: `checkpoint.json` `saved_at` fresh; portfolio_state consistent.
- No duplicate orders: `duplicate fills (genuine double-orders) = 0`.
- No live-trading path: confirmed by `assert_paper` guard + risk status `mode: paper`.

Do NOT change code/strategy to satisfy any of these — investigate and document only.

## Final report (after the 09-11 session close)
Run:

```
cd /home/satyanagesh/Documents/opencode-discord-bot/work/Trading-Bot
poetry run python tools/signal_journal_week_report.py --forward \
    --output reports/SIGNAL_JOURNAL_WEEK_2026-09-07.md
```

`--forward` reads the persisted parquet market-data cache to compute REAL out-of-sample
forward outcomes (post-`data_ts` bars only) for sections K/L. It never fabricates and
declares "N/A" when the sample is below the statistical threshold (MIN_EXPECTANCY_N=30).

Then append the SINGLE highest-value intervention (A..Q + recommendation) based strictly
on the evidence. Choose from: (1) strategy logic, (2) a filter wrongly suppressing,
(3) confidence/optimizer too restrictive, (4) regime classification inappropriate,
(5) data/indicator inputs problematic, (6) execution is the problem, (7) insufficient
evidence — continue collecting. Do NOT "fit" a best threshold or call P&L proof either way.
