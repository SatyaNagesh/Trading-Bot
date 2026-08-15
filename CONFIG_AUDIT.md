# Configuration Audit Report

**Date:** 2026-07-17  
**Scope:** Phase 4.5 — Configuration Audit  
**Total findings:** 18

---

## Summary

| Category          | Count | Severity |
|-------------------|-------|----------|
| HARDCODED SECRET  | 12    | HIGH     |
| HARDCODED PATH    | 2      | MEDIUM   |
| CONFIG OK         | 4      | INFO     |
| **Total**         | **18**|          |

---

## Hardcoded Secrets (12)

| # | File | Line | Detail |
|---|------|------|--------|
| 1 | `packages/broker/gateway.py` | `api_key: str = ""` | Empty default placeholder — acceptable pattern, but should use env var |
| 2 | `packages/broker/gateway.py` | `api_secret: str = ""` | Same as above |
| 3 | `packages/broker/gateway.py` | `access_token: str = ""` | Same as above |
| 4 | `packages/core/config.py` | `secret_key: str = ""` | Config default — should source from env |
| 5 | `packages/core/config.py` | `neo4j_password: str = ""` | Config default |
| 6 | `packages/core/config.py` | `minio_secret_key: str = ""` | Config default |
| 7 | `packages/core/models.py` | `author = Column(String(100), default="")` | Low risk — ORM default for author field |
| 8 | `packages/domain/models.py` | `author: str = ""` | Low risk — default string field |
| 9 | `packages/indicators/evaluator.py` | `elif len(tokens) == 2 and tokens[0] == "not":` | **False positive** — string literal used in expression parser, not a credential |
| 10 | `packages/production/config.py` | `api_key: str = ""` | Config default — should source from env |
| 11 | `packages/tools/config_validate.py` | `"alpaca": BrokerConfig(mode="alpaca", api_key="test", ...)` | Test validation data — uses literal `"test"` value |
| 12 | `packages/tools/config_validate.py` | `"alpaca": BrokerConfig(mode="alpaca", api_key="test", ...)` | Duplicate — same line matched twice |

## Hardcoded Paths (2)

| # | File | Line | Detail |
|---|------|------|--------|
| 1 | `packages/production/config.py` | `dsn: str = "sqlite:///data/quantlab.db"` | Hardcoded database path — should be configurable via env |
| 2 | `packages/tools/config_validate.py` | `assert db.dsn == "sqlite:///data/quantlab.db"` | Test assertion tied to hardcoded path |

## Config Class Health (4)

| # | Class | Fields | Status |
|---|-------|--------|--------|
| 1 | `Settings` | 0 fields | OK — may use `__getattr__` or dynamic attribute resolution |
| 2 | `IntegrationConfig` | 17 fields | OK |
| 3 | `ProductionConfig` | 9 fields | OK |
| 4 | `ScheduleConfig` | 10 fields | OK |

---

## Recommendations

1. **HIGH** — Replace all credential defaults (`api_key`, `api_secret`, `secret_key`, `neo4j_password`, `minio_secret_key`, `access_token`) with `os.environ.get("VAR_NAME", "")` or use a dedicated secrets manager.
2. **MEDIUM** — Make the SQLite DSN configurable via environment variable with a sensible default path under the project directory.
3. **LOW** — Remove the `"test"` literal credentials from `config_validate.py`; use a test fixture or env override instead.
4. **INFO** — The `Settings` class with 0 tracked fields may indicate it relies on `__getattr__`; document the dynamic field contract.
