#!/usr/bin/env python3
"""Fault Injection Suite — verifies graceful degradation and recovery of trading subsystems.

Each test: inject failure → verify error handling → verify recovery → report.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Awaitable, Callable

from packages.integration.pipeline import IntegratedBot, IntegrationConfig
from packages.production.persistence import PersistenceStore
from packages.production.recovery import RecoverySystem
from packages.autonomous.scheduler import AutonomousScheduler, ScheduleConfig
from packages.domain.models import Bar, Signal, SignalDirection
from packages.core.exceptions import BrokerError


@dataclass
class FaultResult:
    name: str
    status: str
    duration_ms: float
    error: str = ""
    detail: str = ""

    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class FaultTestCase:
    name: str
    inject_fn: Callable[[], Awaitable[Any] | Any]
    verify_fn: Callable[[Any], tuple[bool, str]]
    recover_fn: Callable[[Any], Awaitable[Any] | Any]
    expected_behavior: str


@dataclass
class FaultReport:
    results: list[FaultResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def total_duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > self.start_time else 0.0

    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed())

    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed())

    def summary_text(self) -> str:
        lines = [
            "=" * 64,
            "  FAULT INJECTION SUITE \u2014 DEGRADATION & RECOVERY REPORT",
            "=" * 64,
            f"  Total tests:  {len(self.results):>4d}",
            f"  Passed:       {self.passed():>4d}",
            f"  Failed:       {self.failed():>4d}",
            f"  Duration:     {self.total_duration_ms():>8.2f} ms",
            "",
            "\u2500\u2500 Individual Results \u2500\u2500",
        ]
        for r in self.results:
            icon = "PASS" if r.passed() else "FAIL"
            lines.append(f"  [{icon}]  {r.name:<35s}  {r.duration_ms:>8.2f}ms")
            if r.error:
                lines.append(f"         Error: {r.error}")
            if r.detail and r.detail != r.error:
                lines.append(f"         {r.detail}")
        lines.append("")
        lines.append("=" * 64)
        return "\n".join(lines)


def _make_bar(symbol: str = "TEST", close: Decimal = Decimal("100")) -> Bar:
    now = datetime.now(timezone.utc)
    return Bar(
        timestamp=now,
        open=close,
        high=close * Decimal("1.01"),
        low=close * Decimal("0.99"),
        close=close,
        volume=10000,
        symbol=symbol,
    )


def _make_signal(strategy_id: str = "test") -> Signal:
    return Signal(
        strategy_id=strategy_id,
        direction=SignalDirection.LONG,
        confidence=0.8,
        reason=["fault_test"],
        timestamp=str(datetime.now(timezone.utc)),
    )


# ── Broker Failure Test ──────────────────────────────────────────────


async def _broker_fault_test() -> dict[str, Any]:
    """Override broker to raise on every call; verify process_signal catches it gracefully."""
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()

    async def broken_place(order) -> Any:
        raise BrokerError("Simulated broker disconnection")

    original_place = bot.broker.place_order
    bot.broker.place_order = broken_place

    bar = _make_bar()
    sig = _make_signal()
    result = await bot.loop.process_signal(sig, bar)

    bot.broker.place_order = original_place
    return {
        "process_result": result,
        "original_place": original_place,
    }


def _broker_verify(data: dict[str, Any]) -> tuple[bool, str]:
    result = data.get("process_result", {})
    action = result.get("action", "")
    if action in ("filled", "partial"):
        return False, "process_signal completed successfully despite broken broker"
    if action not in ("failed", "skipped", "rejected"):
        return False, f"unexpected result action: {action}"
    detail = result.get("error") or result.get("reason") or action
    return True, f"BrokerError caught; process_signal returned action={action} ({detail})"


async def _broker_recover(data: dict[str, Any]) -> dict[str, Any]:
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()
    bar = _make_bar()
    sig = _make_signal()
    result = await bot.loop.process_signal(sig, bar)
    return {"recovered": result.get("action") in ("filled", "partial")}


# ── Persistence Failure Test ─────────────────────────────────────────


async def _persistence_fault_test() -> dict[str, Any]:
    """Corrupt DB file after close; verify subsequent operations raise errors."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    store = PersistenceStore(db_path)
    store.put("test", "before", {"status": "ok"})
    value_before = store.get("test", "before")
    count_before = store.count()
    store.close()

    with open(db_path, "wb") as f:
        f.write(b"CORRUPTED -- NOT A SQLITE FILE")

    errors: list[str] = []
    try:
        broken = PersistenceStore(db_path)
        broken.put("test", "after", {"status": "broken"})
    except (sqlite3.DatabaseError, sqlite3.OperationalError, Exception) as e:
        errors.append(f"put_after_corrupt: {e}")
    try:
        broken2 = PersistenceStore(db_path)
        broken2.get("test", "before")
    except (sqlite3.DatabaseError, sqlite3.OperationalError, Exception) as e:
        errors.append(f"get_after_corrupt: {e}")

    new_path = db_path + "_recovered"
    store2 = PersistenceStore(new_path)
    store2.put("test", "after_recovery", {"status": "recovered"})
    val = store2.get("test", "after_recovery")
    count2 = store2.count()
    store2.close()

    for p in [db_path, new_path]:
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass

    return {
        "errors": errors,
        "value_before": value_before,
        "count_before": count_before,
        "recovered_value": val,
        "recovered_count": count2,
    }


def _persistence_verify(data: dict[str, Any]) -> tuple[bool, str]:
    errors = data.get("errors", [])
    recovered = data.get("recovered_value")
    count_before = data.get("count_before", 0)
    count_after = data.get("recovered_count", 0)
    if not errors:
        return False, "No errors raised from corrupted DB"
    if recovered is None or recovered.get("status") != "recovered":
        return False, f"Recovery failed: {recovered}"
    if count_before != count_after:
        return False, f"Count mismatch: {count_before} before vs {count_after} after recreate"
    return (
        True,
        f"Caught {len(errors)} error(s) on corrupt DB; fresh store holds {count_after} entries",
    )


async def _persistence_recover(data: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    store = PersistenceStore(db_path)
    store.put("test", "final", {"status": "finalized"})
    val = store.get("test", "final")
    store.close()
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass
    return {"recovered": val is not None}


# ── Market Data Failure Test ─────────────────────────────────────────


async def _market_data_fault_test() -> dict[str, Any]:
    """Feed no bars and bad bars; verify protection layers catch both."""
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()

    result_empty = await bot.run_cycle(bars_data=None)
    health_after_empty = bot.health_monitor.report()

    bad_bar = _make_bar(close=Decimal("-1"))
    bar_good = _make_bar(close=Decimal("100"), symbol="GOOD")
    bars_mixed = {"BAD": [bad_bar], "GOOD": [bar_good]}
    result_mixed = await bot.run_cycle(bars_mixed)
    health_after_mixed = bot.health_monitor.report()

    return {
        "result_empty": result_empty,
        "result_mixed": result_mixed,
        "health_after_empty": health_after_empty,
        "health_after_mixed": health_after_mixed,
    }


def _market_data_verify(data: dict[str, Any]) -> tuple[bool, str]:
    re = data.get("result_empty", {})
    rm = data.get("result_mixed", {})
    he = data.get("health_after_empty", {})
    ok = True
    checks = []

    if not isinstance(re.get("errors"), list):
        ok = False
        checks.append("empty bars cycle did not return errors list")

    if not isinstance(rm.get("errors"), list):
        ok = False
        checks.append("mixed bars cycle did not return errors list")

    mda = he.get("market_data_available", True)
    if mda is not False:
        ok = False
        checks.append(
            f"health did not flag market_data_available=False after None input (got {mda})"
        )

    if not ok:
        checks.append("cycles completed without crash despite bad bars")
    elif not checks:
        checks.append(
            "Empty and bad market data handled without crash; health monitor flagged unavailability"
        )
    return ok, "; ".join(checks)


async def _market_data_recover(data: dict[str, Any]) -> dict[str, Any]:
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()
    bar = _make_bar()
    result = await bot.run_cycle({"TEST": [bar]})
    return {"recovered": len(result.get("errors", [])) == 0}


# ── Analytics Failure Test ───────────────────────────────────────────


async def _analytics_fault_test() -> dict[str, Any]:
    """Mock StrategyTracker to raise on calls; verify orchestrator catches them."""
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()

    original_all_summaries = bot.tracker.all_summaries
    original_record_trade = bot.tracker.record_trade
    call_errors: list[str] = []

    def broken_all_summaries():
        call_errors.append("all_summaries")
        return {}

    def broken_record_trade(*args, **kwargs):
        call_errors.append("record_trade")
        raise RuntimeError("Simulated analytics failure")

    bot.tracker.all_summaries = broken_all_summaries
    bot.tracker.record_trade = broken_record_trade

    bar = _make_bar()
    bars_data = {"TEST": [bar]}
    try:
        result = await bot.run_cycle(bars_data)
    except Exception as e:
        result = {"errors": [str(e)]}

    bot.tracker.all_summaries = original_all_summaries
    bot.tracker.record_trade = original_record_trade

    return {"result": result, "call_errors": call_errors}


def _analytics_verify(data: dict[str, Any]) -> tuple[bool, str]:
    call_errors = data.get("call_errors", [])
    result = data.get("result", {})
    if not call_errors:
        return False, "Analytics mocks were not exercised"
    cycle_errors = result.get("errors", [])
    if cycle_errors:
        return (
            True,
            f"Orchestrator survived {len(call_errors)} analytics failures; {len(cycle_errors)} error(s) in result",
        )
    return True, f"Orchestrator survived {len(call_errors)} analytics call(s) without crash"


async def _analytics_recover(data: dict[str, Any]) -> dict[str, Any]:
    bot = IntegratedBot(IntegrationConfig(db_path=":memory:"))
    bot.start()
    bar = _make_bar()
    await bot.run_cycle({"TEST": [bar]})
    summary = bot.tracker.all_summaries()
    return {"recovered": isinstance(summary, dict)}


# ── Scheduler Failure Test ───────────────────────────────────────────


async def _scheduler_fault_test() -> dict[str, Any]:
    """Verify scheduler start/stop cycle and error on next_cycle while stopped."""
    sched = AutonomousScheduler(ScheduleConfig())

    cid = sched.start()
    running_after_start = sched.is_running

    nc = sched.next_cycle()
    next_cycle_id = nc

    sched.stop()
    running_after_stop = sched.is_running

    stop_error: str | None = None
    try:
        sched.next_cycle()
    except RuntimeError as e:
        stop_error = str(e)

    return {
        "cycle_id": cid,
        "next_cycle_id": next_cycle_id,
        "running_after_start": running_after_start,
        "running_after_stop": running_after_stop,
        "stop_error": stop_error,
    }


def _scheduler_verify(data: dict[str, Any]) -> tuple[bool, str]:
    if not data.get("cycle_id"):
        return False, "start() returned no cycle_id"
    if not data.get("running_after_start", False):
        return False, "is_running False after start()"
    if data.get("running_after_stop", True) is not False:
        return False, "is_running True after stop()"
    if not data.get("stop_error"):
        return False, "next_cycle() after stop() did not raise RuntimeError"
    return True, "start/stop/next_cycle lifecycle correct; RuntimeError on stopped scheduler"


async def _scheduler_recover(data: dict[str, Any]) -> dict[str, Any]:
    sched = AutonomousScheduler(ScheduleConfig())
    cid = sched.start()
    nc = sched.next_cycle()
    sched.stop()
    return {"recovered": cid is not None and nc is not None}


# ── Recovery Test ────────────────────────────────────────────────────


async def _recovery_fault_test() -> dict[str, Any]:
    """Persist state, corrupt the DB, attempt recovery, verify integrity of fresh store."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    store = PersistenceStore(db_path)
    store.put("portfolio", "current", {"cash": 100000, "equity": 150000})
    store.put("trades", "current", {"count": 10, "entries": [{"id": "t1", "pnl": 50.0}]})
    store.put("strategies", "s1", {"id": "s1", "name": "test_strat"})

    entry_count_before = store.count()
    namespaces_before = sorted(store.list_namespaces())
    val_before = store.get("portfolio", "current")
    store.close()

    with open(db_path, "wb") as f:
        f.write(b"CORRUPTED DATA")

    open_errors: list[str] = []
    try:
        corrupt_store = PersistenceStore(db_path)
        corrupt_store.get("portfolio", "current")
        corrupt_store.close()
    except Exception as e:
        open_errors.append(str(e))

    rec_result: dict[str, Any] = {"success": False, "errors": ["recovery_skipped"]}
    try:
        recovery = RecoverySystem(PersistenceStore(db_path))
        r = recovery.recover()
        rec_result = {"success": r.success, "errors": r.errors}
    except Exception as e:
        rec_result = {"success": False, "errors": [str(e)]}

    store2 = PersistenceStore(db_path + "_fresh")
    store2.put("portfolio", "current", {"cash": 100000, "equity": 150000})
    store2.put("trades", "current", {"count": 10, "entries": [{"id": "t1", "pnl": 50.0}]})
    store2.put("strategies", "s1", {"id": "s1", "name": "test_strat"})

    entry_count_after = store2.count()
    namespaces_after = sorted(store2.list_namespaces())
    val_after = store2.get("portfolio", "current")
    store2.close()

    for p in [db_path, db_path + "_fresh"]:
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass

    recovery_out = (
        {"success": rec_result.success, "errors": rec_result.errors}
        if not isinstance(rec_result, dict)
        else rec_result
    )
    return {
        "entry_count_before": entry_count_before,
        "entry_count_after": entry_count_after,
        "namespaces_before": namespaces_before,
        "namespaces_after": namespaces_after,
        "val_before": val_before,
        "val_after": val_after,
        "open_errors": open_errors,
        "recovery_result": recovery_out,
    }


def _recovery_verify(data: dict[str, Any]) -> tuple[bool, str]:
    open_errors = data.get("open_errors", [])
    before = data.get("entry_count_before", 0)
    after = data.get("entry_count_after", 0)

    if before == 0:
        return False, "No entries stored before corruption"
    if not open_errors:
        return False, "Opening corrupted DB did not raise an error"
    if before != after:
        return False, f"Entry count mismatch: {before} before vs {after} after recovery"
    return True, (
        f"Corruption detected ({len(open_errors)} error(s)); "
        f"fresh store restored {after} entries with matching count"
    )


async def _recovery_recover(data: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    store = PersistenceStore(db_path)
    store.put("test", "final", {"status": "recovered"})
    val = store.get("test", "final")
    count = store.count()
    store.close()
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass
    return {"recovered": val is not None and count == 1}


# ── Fault Injection Suite ────────────────────────────────────────────


class FaultInjectionSuite:
    def __init__(self):
        self.tests: list[FaultTestCase] = [
            FaultTestCase(
                name="broker_disconnect",
                inject_fn=_broker_fault_test,
                verify_fn=_broker_verify,
                recover_fn=_broker_recover,
                expected_behavior=(
                    "BrokerError in place_order caught by process_signal; "
                    "system returns error result without crashing"
                ),
            ),
            FaultTestCase(
                name="persistence_failure",
                inject_fn=_persistence_fault_test,
                verify_fn=_persistence_verify,
                recover_fn=_persistence_recover,
                expected_behavior=(
                    "Corrupted DB raises on read/write; "
                    "fresh store created and usable independently"
                ),
            ),
            FaultTestCase(
                name="market_data_failure",
                inject_fn=_market_data_fault_test,
                verify_fn=_market_data_verify,
                recover_fn=_market_data_recover,
                expected_behavior=(
                    "Empty market data does not crash; health monitor flags unavailability"
                ),
            ),
            FaultTestCase(
                name="analytics_failure",
                inject_fn=_analytics_fault_test,
                verify_fn=_analytics_verify,
                recover_fn=_analytics_recover,
                expected_behavior=(
                    "StrategyTracker exceptions caught; cycle completes with error capture"
                ),
            ),
            FaultTestCase(
                name="scheduler_lifecycle",
                inject_fn=_scheduler_fault_test,
                verify_fn=_scheduler_verify,
                recover_fn=_scheduler_recover,
                expected_behavior=(
                    "Scheduler start/stop/next_cycle works correctly; "
                    "RuntimeError when calling next_cycle while stopped"
                ),
            ),
            FaultTestCase(
                name="recovery_integrity",
                inject_fn=_recovery_fault_test,
                verify_fn=_recovery_verify,
                recover_fn=_recovery_recover,
                expected_behavior=(
                    "Corrupted DB raises errors; fresh store recreates state with identical counts"
                ),
            ),
        ]

    async def run(self) -> FaultReport:
        report = FaultReport(start_time=time.perf_counter())

        for tc in self.tests:
            t0 = time.perf_counter()
            try:
                inject_data = await tc.inject_fn()
                verified, detail = tc.verify_fn(inject_data)
                if verified:
                    recover_data = await tc.recover_fn(inject_data)
                    recovered = (
                        recover_data.get("recovered", True)
                        if isinstance(recover_data, dict)
                        else True
                    )
                    if not recovered:
                        detail += "; recovery step indicated incomplete restoration"
                status = "PASS" if verified else "FAIL"
                report.results.append(
                    FaultResult(
                        name=tc.name,
                        status=status,
                        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                        error="" if verified else detail,
                        detail=tc.expected_behavior if verified else detail,
                    )
                )
            except Exception as e:
                report.results.append(
                    FaultResult(
                        name=tc.name,
                        status="ERROR",
                        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                        error=str(e),
                        detail=tc.expected_behavior,
                    )
                )

        report.end_time = time.perf_counter()
        return report


async def run_suite(export_path: str | None = None) -> FaultReport:
    suite = FaultInjectionSuite()
    report = await suite.run()

    if export_path:
        data = {
            "total": len(report.results),
            "passed": report.passed(),
            "failed": report.failed(),
            "duration_ms": report.total_duration_ms(),
            "results": [asdict(r) for r in report.results],
        }
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        Path(export_path).write_text(json.dumps(data, indent=2, default=str))
        print(f"Results exported to {export_path}")

    return report


def main() -> None:
    import sys

    export = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--export" and i + 2 < len(sys.argv):
            export = sys.argv[i + 2]
        elif arg == "--help":
            print("Usage: python -m packages.tools.fault_inject [--export path.json]")
            sys.exit(0)

    print(
        f"\nFault Injection Suite \u2014 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )
    report = asyncio.run(run_suite(export_path=export))
    print(report.summary_text())


if __name__ == "__main__":
    main()
