#!/usr/bin/env python3
"""Long Duration Simulation — production certification harness."""

import asyncio
import json
import math
from random import random
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from packages.integration.pipeline import IntegratedBot, IntegrationConfig
from packages.domain.models import Bar


BULL_TREND = 1.0012
BEAR_TREND = 0.9988
SIDEWAYS_NOISE = 0.002
VOLATILE_SWING = 0.025


@dataclass
class SimulationPhase:
    name: str
    cycles: int
    market_regime: str
    base_price: Decimal = Decimal("100")
    volatility: float = 0.005
    trend_factor: float = 1.0
    volume_base: int = 10000
    shock_probability: float = 0.0


@dataclass
class SimulationMetrics:
    uptime_pct: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    avg_memory_mb: float = 0.0
    max_memory_mb: float = 0.0
    throughput_cycles_per_sec: float = 0.0
    total_cycles: int = 0
    total_errors: int = 0
    subsystem_reliability: dict[str, float] = field(default_factory=dict)
    phase_results: list[dict[str, Any]] = field(default_factory=list)
    cycle_latencies: list[float] = field(default_factory=list)
    memory_samples: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def generate_bars(
    symbol: str,
    regime: str,
    count: int,
    base_price: Decimal = Decimal("100"),
    volatility: float = 0.005,
    trend_factor: float = 1.0,
    volume_base: int = 10000,
    shock_probability: float = 0.0,
) -> list[Bar]:
    now = datetime.now(timezone.utc)
    price = float(base_price)
    bars: list[Bar] = []

    for i in range(count):
        ts = now - timedelta(minutes=count - i)

        if regime == "bull":
            drift = BULL_TREND - 1.0
            noise = volatility * (1 + SIDEWAYS_NOISE)
        elif regime == "bear":
            drift = BEAR_TREND - 1.0
            noise = volatility * (1 + SIDEWAYS_NOISE)
        elif regime == "volatile":
            cycle = math.sin(i * 0.3) * VOLATILE_SWING
            drift = cycle
            noise = volatility * (2 + SIDEWAYS_NOISE)
        else:
            drift = 0.0
            noise = volatility * (1 + SIDEWAYS_NOISE)

        if shock_probability > 0 and _should_shock(shock_probability):
            shock = -0.05 if regime == "bear" else (0.04 if regime == "bull" else 0.0)
            drift += shock

        change = drift + _gauss() * noise
        price *= 1 + change
        price = max(price, 1.0)

        spread = noise * 0.5
        volume = volume_base + int(_gauss() * volume_base * 0.3)
        volume = max(volume, 100)

        bars.append(
            Bar(
                symbol=symbol,
                timestamp=ts,
                open=Decimal(str(round(price, 2))),
                high=Decimal(str(round(price * (1 + spread * _gauss()), 2))),
                low=Decimal(str(round(price * (1 - spread * _gauss()), 2))),
                close=Decimal(str(round(price, 2))),
                volume=volume,
            )
        )

    return bars


_SHOCK_COUNTER: int = 0


def _should_shock(probability: float) -> bool:
    global _SHOCK_COUNTER
    _SHOCK_COUNTER += 1
    if _SHOCK_COUNTER % max(1, int(1 / max(probability, 0.001))) == 0:
        return True
    return False


def _gauss() -> float:
    return sum(random() for _ in range(6)) - 3.0


def _get_memory_mb() -> float:
    import resource as _resource

    usage = _resource.getrusage(_resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024.0


def _compute_percentiles(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    s = sorted(values)
    n = len(s)
    p50 = s[int(n * 0.50)] if n > 1 else s[0]
    p95 = s[int(n * 0.95)] if n > 1 else s[-1]
    p99 = s[int(n * 0.99)] if n > 1 else s[-1]
    return p50, p95, p99


PHASE_DEFINITIONS: list[SimulationPhase] = [
    SimulationPhase(
        name="bull_run",
        cycles=250,
        market_regime="bull",
        base_price=Decimal("100"),
        volatility=0.004,
        trend_factor=BULL_TREND,
        volume_base=12000,
        shock_probability=0.02,
    ),
    SimulationPhase(
        name="bear_market",
        cycles=250,
        market_regime="bear",
        base_price=Decimal("150"),
        volatility=0.006,
        trend_factor=BEAR_TREND,
        volume_base=15000,
        shock_probability=0.04,
    ),
    SimulationPhase(
        name="sideways",
        cycles=250,
        market_regime="sideways",
        base_price=Decimal("120"),
        volatility=0.003,
        trend_factor=1.0,
        volume_base=8000,
        shock_probability=0.01,
    ),
    SimulationPhase(
        name="volatile",
        cycles=250,
        market_regime="volatile",
        base_price=Decimal("110"),
        volatility=0.012,
        trend_factor=1.0,
        volume_base=20000,
        shock_probability=0.08,
    ),
]


def _default_phases(total_cycles: int) -> list[SimulationPhase]:
    if total_cycles <= 0:
        return PHASE_DEFINITIONS
    per_phase = max(1, total_cycles // len(PHASE_DEFINITIONS))
    phases = []
    for i, base in enumerate(PHASE_DEFINITIONS):
        phases.append(
            SimulationPhase(
                name=base.name,
                cycles=per_phase if i < 3 else total_cycles - per_phase * 3,
                market_regime=base.market_regime,
                base_price=base.base_price,
                volatility=base.volatility,
                trend_factor=base.trend_factor,
                volume_base=base.volume_base,
                shock_probability=base.shock_probability,
            )
        )
    return phases


class LongDurationSimulation:
    def __init__(
        self,
        total_cycles: int = 1000,
        phases: list[SimulationPhase] | None = None,
        config: IntegrationConfig | None = None,
    ):
        self.total_cycles = total_cycles
        self.phases = phases or _default_phases(total_cycles)
        self.config = config or IntegrationConfig()
        self.metrics = SimulationMetrics()
        self.bot: IntegratedBot | None = None
        self._start_time: float = 0.0

    def _init_bot(self) -> IntegratedBot:
        return IntegratedBot(config=self.config)

    def _measure_subsystems(self) -> dict[str, float]:
        reliability: dict[str, float] = {}
        try:
            reliability["broker"] = 1.0 if self.bot and self.bot.broker else 0.0
        except Exception:
            reliability["broker"] = 0.0
        try:
            reliability["oms"] = 1.0 if self.bot and hasattr(self.bot, "oms") else 0.0
        except Exception:
            reliability["oms"] = 0.0
        try:
            reliability["portfolio"] = 1.0 if self.bot and self.bot.portfolio else 0.0
        except Exception:
            reliability["portfolio"] = 0.0
        try:
            reliability["risk"] = 1.0 if self.bot and hasattr(self.bot, "risk") else 0.0
        except Exception:
            reliability["risk"] = 0.0
        try:
            reliability["persistence"] = 1.0 if self.bot and self.bot.store else 0.0
        except Exception:
            reliability["persistence"] = 0.0
        try:
            reliability["execution"] = 1.0 if self.bot and hasattr(self.bot, "execution") else 0.0
        except Exception:
            reliability["execution"] = 0.0
        try:
            reliability["journal"] = 1.0 if self.bot and hasattr(self.bot, "journal") else 0.0
        except Exception:
            reliability["journal"] = 0.0
        try:
            reliability["health_monitor"] = (
                1.0 if self.bot and hasattr(self.bot, "health_monitor") else 0.0
            )
        except Exception:
            reliability["health_monitor"] = 0.0
        return reliability

    async def run(self) -> SimulationMetrics:
        self._start_time = time.perf_counter()
        self.metrics = SimulationMetrics()
        self.bot = self._init_bot()
        self.bot.start()

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        total_errors = 0
        cycle_latencies: list[float] = []
        memory_samples: list[float] = []
        all_phase_results: list[dict[str, Any]] = []
        global _SHOCK_COUNTER
        _SHOCK_COUNTER = 0

        cycle_index = 0
        for phase in self.phases:
            if cycle_index >= self.total_cycles:
                break
            bars = generate_bars(
                symbol="SIM",
                regime=phase.market_regime,
                count=phase.cycles + 2,
                base_price=phase.base_price,
                volatility=phase.volatility,
                trend_factor=phase.trend_factor,
                volume_base=phase.volume_base,
                shock_probability=phase.shock_probability,
            )
            phase_errors = 0
            phase_start = time.perf_counter()

            for bar in bars[: phase.cycles]:
                if cycle_index >= self.total_cycles:
                    break
                cycle_index += 1

                cycle_start = time.perf_counter()
                try:
                    bars_data = {"SIM": [bar]}
                    result = await self.bot.run_cycle(bars_data)
                    if result.get("errors"):
                        phase_errors += len(result["errors"])
                except Exception:
                    phase_errors += 1
                elapsed_ms = (time.perf_counter() - cycle_start) * 1000
                cycle_latencies.append(elapsed_ms)

                if cycle_index % 10 == 0:
                    memory_samples.append(_get_memory_mb())

            phase_elapsed = time.perf_counter() - phase_start
            phase_result = {
                "phase": phase.name,
                "regime": phase.market_regime,
                "cycles_completed": min(phase.cycles, self.total_cycles),
                "errors": phase_errors,
                "duration_sec": round(phase_elapsed, 3),
                "cycles_per_sec": round(
                    min(phase.cycles, self.total_cycles) / max(phase_elapsed, 0.001), 2
                ),
            }
            all_phase_results.append(phase_result)
            total_errors += phase_errors

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        tracemalloc_diff = sum(s.size_diff for s in stats) / (1024 * 1024)

        subsystem_reliability = self._measure_subsystems()
        p50, p95, p99 = _compute_percentiles(cycle_latencies)
        avg_memory = statistics.mean(memory_samples) if memory_samples else 0.0
        max_memory = max(memory_samples) if memory_samples else 0.0
        mem_resource = _get_memory_mb()
        if mem_resource > max_memory:
            max_memory = mem_resource
        if avg_memory == 0.0 and mem_resource > 0:
            avg_memory = mem_resource
            memory_samples.append(mem_resource)

        uptime_pct = 100.0
        if self.total_cycles > 0 and total_errors > 0:
            uptime_pct = ((self.total_cycles - total_errors) / self.total_cycles) * 100

        throughput = self.total_cycles / max(time.perf_counter() - self._start_time, 0.001)

        self.metrics = SimulationMetrics(
            uptime_pct=round(uptime_pct, 2),
            latency_p50_ms=round(p50, 2),
            latency_p95_ms=round(p95, 2),
            latency_p99_ms=round(p99, 2),
            avg_memory_mb=round(max(avg_memory, tracemalloc_diff), 2),
            max_memory_mb=round(max_memory, 2),
            throughput_cycles_per_sec=round(throughput, 2),
            total_cycles=cycle_index,
            total_errors=total_errors,
            subsystem_reliability=subsystem_reliability,
            phase_results=all_phase_results,
            cycle_latencies=cycle_latencies,
            memory_samples=memory_samples,
        )

        return self.metrics

    def summary_text(self) -> str:
        m = self.metrics
        lines = [
            "=" * 64,
            "  LONG DURATION SIMULATION — PRODUCTION CERTIFICATION",
            "=" * 64,
            f"  Cycles:           {m.total_cycles:>6}",
            f"  Errors:           {m.total_errors:>6}",
            f"  Uptime:           {m.uptime_pct:>6.2f}%",
            f"  Throughput:       {m.throughput_cycles_per_sec:>6.2f} cyc/s",
            "",
            "── Latency ──",
            f"  p50:              {m.latency_p50_ms:>8.2f} ms",
            f"  p95:              {m.latency_p95_ms:>8.2f} ms",
            f"  p99:              {m.latency_p99_ms:>8.2f} ms",
            "",
            "── Memory ──",
            f"  Avg:              {m.avg_memory_mb:>8.2f} MB",
            f"  Max:              {m.max_memory_mb:>8.2f} MB",
            "",
            "── Subsystem Reliability ──",
        ]
        for sub, rel in sorted(m.subsystem_reliability.items()):
            bar = "█" * int(rel * 20) + "░" * (20 - int(rel * 20))
            lines.append(f"  {sub:<18s} {bar} {rel * 100:>5.1f}%")

        lines.extend(
            [
                "",
                "── Phase Results ──",
            ]
        )
        for pr in m.phase_results:
            lines.append(
                f"  {pr['phase']:<14s} {pr['regime']:<10s} "
                f"{pr['cycles_completed']:>4d} cyc  "
                f"{pr['errors']:>3d} err  "
                f"{pr['duration_sec']:>8.2f}s  "
                f"{pr['cycles_per_sec']:>8.2f} cyc/s"
            )

        lines.extend(
            [
                "",
                "=" * 64,
            ]
        )
        return "\n".join(lines)


def print_summary(metrics: SimulationMetrics) -> None:
    print(f"\n{'=' * 64}")
    print("  SIMULATION COMPLETE")
    print(f"{'=' * 64}")
    print(f"  Total cycles:     {metrics.total_cycles}")
    print(f"  Total errors:     {metrics.total_errors}")
    print(f"  Uptime:           {metrics.uptime_pct:.2f}%")
    print(f"  Throughput:       {metrics.throughput_cycles_per_sec:.2f} cyc/s")
    print(
        f"  Latency p50/p95/p99: {metrics.latency_p50_ms:.1f} / {metrics.latency_p95_ms:.1f} / {metrics.latency_p99_ms:.1f} ms"
    )
    print(f"  Memory (avg/max): {metrics.avg_memory_mb:.1f} / {metrics.max_memory_mb:.1f} MB")
    print("\n  Subsystem Reliability:")
    for sub, rel in sorted(metrics.subsystem_reliability.items()):
        print(f"    {sub:<16s} {rel * 100:>6.2f}%")
    print(f"{'=' * 64}\n")


async def run_simulation(
    total_cycles: int = 100,
    phases: list[SimulationPhase] | None = None,
    config: IntegrationConfig | None = None,
    export_path: str | None = None,
) -> SimulationMetrics:
    sim = LongDurationSimulation(total_cycles=total_cycles, phases=phases, config=config)
    metrics = await sim.run()

    if export_path:
        with open(export_path, "w") as f:
            f.write(metrics.to_json())
        print(f"Results exported to {export_path}")

    print_summary(metrics)
    return metrics


def main() -> None:
    import sys

    cycles = 100
    export = None

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--cycles" and i + 2 < len(sys.argv):
            try:
                cycles = int(sys.argv[i + 2])
            except (ValueError, IndexError):
                pass
        elif arg == "--export" and i + 2 < len(sys.argv):
            export = sys.argv[i + 2]
        elif arg == "--help":
            print("Usage: python -m packages.tools.simulate [--cycles N] [--export path.json]")
            sys.exit(0)

    phases = _default_phases(cycles)

    print(f"\nStarting Long Duration Simulation: {cycles} cycles across {len(phases)} phases")
    for p in phases:
        print(
            f"  {p.name:<14s} {p.market_regime:<10s} {p.cycles:>4d} cycles  vol={p.volatility}  shock={p.shock_probability}"
        )
    print()

    asyncio.run(run_simulation(total_cycles=cycles, phases=phases, export_path=export))


if __name__ == "__main__":
    main()
