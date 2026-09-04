# Signal Journal — Week-Long Out-of-Sample Collection (2026-09-07)

**Status: COLLECTION PENDING — no genuine candidates recorded yet.**

The runtime is running and instrumented, but the NSE sessions for the
collection window (beginning Mon 2026-09-07) have not yet elapsed in real
time. This report NEVER fabricates outcomes. Re-run this generator after
the final planned observation session to populate A..Q from real data.

If you are re-reading this after the sessions and still see zero records,
first verify the runtime was actually running during the NSE window (09:15-15:30 IST, weekdays) and that `data/signal_journal.jsonl` exists.

---

## Per-session observation-only checkpoint log

Populate this after each session by running the health check in the runbook
(`reports/NEXT_WEEK_COLLECTION_RUNBOOK_2026-09-07.md`). All rows must be clean.

| Session | candidates | accepted | suppressed | duplicate fills | runtime | mode | notes |
|---|---|---|---|---|---|---|---|
| Mon 09-07 | — | — | — | 0 | — | paper | _collection pending_ |
| Tue 09-08 | — | — | — | 0 | — | paper | _collection pending_ |
| Wed 09-09 | — | — | — | 0 | — | paper | _collection pending_ |
| Thu 09-10 | — | — | — | 0 | — | paper | _collection pending_ |
| Fri 09-11 | — | — | — | 0 | — | paper | _collection pending_ |

At the close of the FINAL session re-run the generator with `--forward` to
populate A..Q from real data:

```
poetry run python tools/signal_journal_week_report.py --forward \
    --output reports/SIGNAL_JOURNAL_WEEK_2026-09-07.md
```

---

## Recommendation (SINGLE highest-value intervention)

**To be completed from the evidence after the final session.** Choose based on the
dominant evidence in A..Q, not intuition. Candidate choices (pick exactly one):
1. Strategy logic genuinely needs improvement.
2. A filter is incorrectly suppressing candidates.
3. Confidence/optimizer behavior is too restrictive.
4. Regime classification is inappropriate.
5. Data/indicator inputs are problematic.
6. Execution is the problem.
7. Insufficient evidence — continue collection.

Do NOT optimize on these observations or select a "best" threshold. Do not call
positive P&L proof of profitability, nor zero P&L proof of failure.
