# Research and Strategy Status

## Authoritative registry

`packages/strategies/registry.py` is the **single source of truth** for
strategy status (data: `data/strategy_registry.json`). The legacy
`data/strategies.json` is **not authoritative**; its `active`/`candidate`/
`watchlist` statuses map to RESEARCH unless the registry says otherwise.

## States and gates

```
RESEARCH -> VALIDATED -> PAPER_APPROVED -> LIVE_APPROVED
   |            |              |               |
 RETIRED     RETIRED        RETIRED         RETIRED
```

- RESEARCH → VALIDATED requires a positive independent validation artifact.
- VALIDATED → PAPER_APPROVED requires a recorded paper-approval decision.
- PAPER_APPROVED → LIVE_APPROVED requires a recorded live-approval decision.
- Every approval transition requires recorded evidence (`authority` + `at`).
  Without evidence the transition **raises**; approval is never fabricated.

## Truth table (2026-09-13)

| Strategy | Authoritative state | Reason |
|---|---|---|
| `autonomous_momentum` | **RESEARCH** | Reconstructed decision path only; no gate decision ever recorded |
| `sma_crossover` | **RESEARCH** | stdlib candidate; never validated |
| `ema_trend` | **RESEARCH** | stdlib candidate; never validated |
| `rsi_mean_reversion` | **RESEARCH** | stdlib candidate; never validated |
| `COMP3_STRATEGY_V1` | **RETIRED** | Program closed; rejected in review |
| `COMP3_STRATEGY_V2` | **RETIRED** | Program closed; paper gate CLOSED (holdout-5 reproduced, grade D, concentration-fragile) |
| `paper-reversal` | **RESEARCH (fixture)** | Simulation fixture for paper engine exercises |
| `default` | **RESEARCH (fixture)** | Coin-flip simulation signal in IntegratedBot |

## Research → strategy separation

- `packages/research/` holds historical evidence and verification tooling
  (e.g. `verify_comp3_program.py`, baseline reconstructions). It does not
  approve anything.
- `packages/strategies/` holds the registry, runner, and candidate tooling.
- `packages/integration/pipeline.py` (`IntegratedBot`) is the autonomous
  RESEARCH sandbox; its default signal is an explicit simulation fixture and
  its auto-promotion path must not be treated as approval — the registry is
  the only source of truth.
- `packages/discovery/` is the (unimplemented) QuantLab Scout scaffold. Out of
  scope for this release.

## Guards

- No unproven strategy may reach PAPER_APPROVED/LIVE_APPROVED: the registry
  enforces evidence + transition graph, and tests assert the ground truth.
- COMP3 must not be revived (program CLOSED, `COMP3_PROGRAM_CLOSEOUT_2026-09.md`).
- "ENGINE READY ≠ STRATEGY EDGE PROVEN": running the paper engine says nothing
  about whether a strategy will make money.