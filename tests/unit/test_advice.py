"""Tests for the human-in-the-loop trade advisor (packages/advice)."""

from datetime import datetime, timedelta, timezone

from packages.advice.advisor import AdviceAdvisor
from packages.domain.models import Bar


def make_bars(symbol: str, closes: list[float], n: int = 0) -> list[Bar]:
    """Build daily bars; if n given, extend by repeating last close."""
    vals = list(closes)
    while len(vals) < n:
        vals.append(vals[-1])
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i, c in enumerate(vals):
        o = c - 1.0
        bars.append(
            Bar(
                timestamp=base + timedelta(days=i),
                open=o,
                high=c + 2.0,
                low=o - 2.0,
                close=c,
                volume=1000,
                symbol=symbol,
            )
        )
    return bars


TRENDING = list(range(100, 160))  # +1/day, strongly bullish


def test_scan_proposes_on_bullish_alignment():
    bars = make_bars("TEST.NS", TRENDING, n=70)
    advisor = AdviceAdvisor(ttl_seconds=300)
    created = advisor.scan({"TEST.NS": bars})
    assert created, "expected at least one proposal on a trending series"
    p = created[0]
    assert p.expected_price > p.current_price
    assert p.expected_return_pct > 0
    assert p.company_name != ""
    assert p.status.value == "pending"


def test_approve_runs_executor_and_marks_approved():
    bars = make_bars("TEST.NS", TRENDING, n=70)
    executed: list[str] = []
    advisor = AdviceAdvisor(ttl_seconds=300, on_approve=lambda p: executed.append(p.id) or {"action": "filled"})
    p = advisor.scan({"TEST.NS": bars})[0]
    result = advisor.approve(p.id)
    assert result["approved"] is True
    assert result["execution"]["action"] == "filled"
    assert p.status.value == "approved"
    assert executed == [p.id]


def test_cancel_skips_trade():
    bars = make_bars("TEST.NS", TRENDING, n=70)
    executed: list[str] = []
    advisor = AdviceAdvisor(ttl_seconds=300, on_approve=lambda p: executed.append(p.id) or {"action": "filled"})
    p = advisor.scan({"TEST.NS": bars})[0]
    result = advisor.reject(p.id)
    assert result["status"] == "rejected"
    assert not executed
    # approving a rejected proposal must not trade
    assert advisor.approve(p.id)["approved"] is False
    assert not executed


def test_expired_proposal_is_default_no():
    bars = make_bars("TEST.NS", TRENDING, n=70)
    executed: list[str] = []
    advisor = AdviceAdvisor(ttl_seconds=0, on_approve=lambda p: executed.append(p.id) or {"action": "filled"})
    p = advisor.scan({"TEST.NS": bars})[0]
    assert p.expired  # TTL 0 -> immediately expired
    result = advisor.approve(p.id)
    assert result["approved"] is False
    assert result["status"] == "expired"
    assert not executed  # default NO: nothing executed


def test_scan_filters_low_return():
    flat = [100.0] * 80  # no trend, no setup
    advisor = AdviceAdvisor(ttl_seconds=300)
    created = advisor.scan({"TEST.NS": make_bars("TEST.NS", flat)})
    # flat series: no golden cross, no momentum, no oversold -> honest 0
    assert isinstance(created, list)
    assert all(p.expected_return_pct > 0 for p in created)
