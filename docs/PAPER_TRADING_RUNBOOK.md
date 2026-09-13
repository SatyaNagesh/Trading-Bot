# Paper Trading Runbook

The paper engine is the active, tested runtime of QuantLab Trader. It executes
orders against `PaperBroker`/`SimulatedBroker` only. No real order can be
placed: every live broker path fails closed unless
`QUANTLAB_LIVE_TRADING_ENABLED=1` is set (see
`SAFETY_AND_LIVE_TRADING.md`).

## Controlled paper E2E check

The canonical verification script (deterministic synthetic NSE-style bars, no
external data):

```bash
poetry run python packages/tools/paper_e2e_check.py
```

It runs 3 symbols x 60 bars for fills, plus a 2000-cycle soak, then writes
`reports/paper_e2e_check_results.json`. Exit code 0 means both integrity checks
passed.

Expected invariants:
- `integrity_verified == true` after every run
- All fills pass through risk (`total_rejected == 0` under normal budget)
- Journal entries == closed round-trips

## Programmatic usage

```python
from decimal import Decimal
from packages.trading.loop import PaperTradingLoop
from packages.broker.gateway import BrokerConfig, PaperBroker
from packages.domain.models import Signal, SignalDirection

loop = PaperTradingLoop(
    broker=PaperBroker(BrokerConfig(mode="paper")),
    initial_capital=Decimal("1000000"),
)

def strategy(bar, ctx):
    return [Signal(strategy_id="demo", direction=SignalDirection.LONG, confidence=0.6)]

loop.set_strategy(strategy)

# Feed bars (your market-data source) one at a time, then inspect:
loop.portfolio.verify_integrity()
loop.status()          # full snapshot: portfolio/risk/session/health/journal/orders
loop.risk.summary()    # kill switch state, rejected orders
loop.health.report()   # broker/data/risk/integrity health
```

## Session gate

- The session gate is evaluated in **Asia/Kolkata** (exchange local time).
  Naive datetimes are treated as UTC and converted.
- 24/7 paper trading is only valid for genuinely 24/7 instruments. Do not fake
  NSE hours; use a custom `MarketCalendar` for non-NSE instruments.
- To test outside market hours you must pass a calendar whose window includes
  your run window — never monkeypatch `session.is_open` in production code.

## Sizing and risk

- Sizing is 2% of available cash per order by default.
- Every order passes the risk engine: position count, size, exposure,
  drawdown, daily loss, leverage, per-strategy allocation, kill switch.
- Paper-article quirk: an exit signal sizes a chunk from cash (2%), so a
  partial close leaves a residual position; close explicitly or use a
  position-aware signal like the one in `packages/tools/paper_e2e_check.py`.