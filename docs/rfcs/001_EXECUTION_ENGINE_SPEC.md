# RFC-001: Execution Engine Specification

> **Status**: Draft | **Author**: Architecture Review | **Date**: July 2026

## Problem

Doc 35 lists "Execution Engine" as one of the 17 engines, but there is no dedicated specification document. Doc 28 (Broker Integration Spec) covers broker abstraction but not the execution layer itself — order routing, execution algorithms (TWAP/VWAP/Iceberg), smart order routing, fill-or-kill logic, and partial fill management are undefined.

## Proposed Solution

Create `docs/36_EXECUTION_ENGINE_SPEC.md` covering:

### Architecture

```
Execution Engine
├── OrderRouter        — Route orders to optimal broker/venue
├── ExecutionAlgo      — TWAP, VWAP, Iceberg, POV algorithms
├── SmartOrderRouter   — Multi-venue order splitting
├── OrderManager       — Order lifecycle (New→Ack→Fill→Partial→Cancel→Reject)
└── FillManager        — Fill aggregation, partial fill handling
```

### Key Interfaces

```python
class ExecutionEngine:
    async def execute(self, order: OrderRequest) -> OrderResult: ...
    async def cancel(self, order_id: str) -> bool: ...
    async def get_status(self, order_id: str) -> OrderStatus: ...
    async def get_open_orders(self) -> list[Order]: ...
```

### Execution Algorithms

| Algorithm | Use Case | Complexity |
|-----------|----------|------------|
| Market Order | Immediate fill | O(1) |
| Limit Order | Price improvement | O(1) |
| TWAP | Time-sliced large orders | O(n) |
| VWAP | Volume-weighted execution | O(n) |
| Iceberg | Hidden large orders | O(1) |
| POV | Participation rate | O(n) |

### Order Lifecycle

```
Created → Validated → Submitted → Pending → 
  ├── Filled (partial or full)
  ├── Cancelled
  └── Rejected
```

### Dependencies

- Broker Gateway (doc 28) — for actual order submission
- Risk Engine (doc 32) — for pre-trade risk checks
- Portfolio Engine (doc 34) — for allocation instructions

## Action

- [ ] Create doc 36 with full 10-section spec
- [ ] Update doc 35 to reference doc 36
- [ ] Update doc 28 to clarify Broker Gateway vs Execution Engine boundary
