# Safety and Live Trading

## Live trading is CLOSED

Live (real-broker) trading is **disabled by default and fails closed**. The
only ways to reach a real broker are:

1. Set `QUANTLAB_LIVE_TRADING_ENABLED=1` in the environment explicitly, and
2. Choose an explicit live broker mode (`zerodha`, `alpaca`, or `angel`).

Without that env var:
- `create_broker(BrokerConfig(mode="zerodha"|"alpaca"|"angel"))` raises
  `ConfigurationError`.
- `ExecutionEngine.execute()` refuses to run on any broker flagged
  `live_capable`.
- `mode="live"` is rejected as ambiguous (there is no silent SimulatedBroker
  fallback anymore).

## Guards implemented in this release

| Guard | Where |
|---|---|
| Live broker factory gate | `packages/broker/gateway.py:create_broker` |
| Execution-time live gate | `packages/execution/engine.py:execute` |
| `live_capable` flag on real brokers | `zerodha.py`, `angel.py`, `gateway.py` (Alpaca) |
| Fail-closed on missing `httpx` | `zerodha.py`, `angel.py` (no simulated FILL for a real broker) |
| Kill switch | `RiskEngine.emergency_stop`/`kill_switch` — blocks all orders |
| Health-critical pause | `HealthMonitor` pauses trading on any critical condition |
| Registry approval gate | strategies cannot reach PAPER/LIVE without recorded decision evidence |

## Secrets and configuration

- Broker credentials live in `BrokerConfig` / environment only. Never commit
  real API keys, tokens, or secrets.
- `.env` is ignored; runtime config comes from env + `config.yaml`
  (`ProductionConfig`).
- The API control plane (`services/api`) guards endpoints with an API key
  (Bearer, constant-time compare) and a rate limiter. Both are optional at
  present; never expose the API to the public internet without enforcing auth.

## API/CORS caveats

- `services/api/main.py` currently configures `allow_origins=["*"]`. This is
  acceptable only for a local/research control plane. Any internet-exposed
  deployment MUST:
  - scope CORS to known origins,
  - force `require_auth` (not `optional_auth`),
  - terminate at a TLS reverse proxy.

## Enabling live trading (NOT recommended; future work)

1. Review the registry: every strategy involved must be at least
   `PAPER_APPROVED`, and any live order stream must come from a
   `LIVE_APPROVED` strategy (see `RESEARCH_AND_STRATEGY_STATUS.md`).
2. Set `QUANTLAB_LIVE_TRADING_ENABLED=1` and provide credentials.
3. Tighten API auth + CORS.
4. Run a supervised, small, fail-closed pilot before any autonomous live leg.

Until all four are done, treat any attempt to trade live as a configuration
error — by design it will raise.

## Verify the guard

```bash
QUANTLAB_LIVE_TRADING_ENABLED= python -c "from packages.broker.gateway import create_broker, BrokerConfig; create_broker(BrokerConfig(mode='zerodha'))"
# -> ConfigurationError: Live trading is CLOSED...
QUANTLAB_LIVE_TRADING_ENABLED=1 python -c "from packages.broker.gateway import create_broker, BrokerConfig; print(create_broker(BrokerConfig(mode='zerodha', api_key='k', access_token='t')))"
# -> builds a ZerodhaBroker (structure only; still no live connection in tests)
```