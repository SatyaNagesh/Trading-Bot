"""/advice — human-in-the-loop trade proposals & approval."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packages.advice.advisor import AdviceAdvisor
from packages.advice.models import TradeProposal
from packages.domain.models import Bar, Signal, SignalDirection
from services.api.dependencies import get_bot_started, get_bot_instance
from services.api.schemas import AdviceScanRequest

router = APIRouter(prefix="/advice", tags=["Advice"])

_advisor: AdviceAdvisor | None = None


def get_advisor() -> AdviceAdvisor:
    global _advisor
    if _advisor is None:
        _advisor = AdviceAdvisor()
    return _advisor


def _parse_bars(body_bars: dict[str, list[dict[str, Any]]]) -> dict[str, list[Bar]]:
    return {sym: [Bar(**b) for b in bar_list] for sym, bar_list in body_bars.items()}


def _signal_for(p: TradeProposal) -> Signal:
    return Signal(
        strategy_id=f"advisor:{p.strategy}",
        symbol=p.symbol,
        direction=SignalDirection.LONG,
        confidence=p.confidence,
        reason=[f"advisor-approval:{p.id}:{p.reason}"],
        timestamp=str(p.created_at),
    )


def _bar_for(p: TradeProposal) -> Bar:
    return Bar(
        timestamp=p.created_at,
        open=p.current_price,
        high=max(p.current_price, p.expected_price),
        low=min(p.current_price, p.stop_price),
        close=p.current_price,
        volume=1,
        symbol=p.symbol,
    )


async def _execute(p: TradeProposal, bot) -> dict[str, Any]:
    """Run the approved proposal's trade through the bot's loop (fills if market open)."""
    try:
        return await bot.loop.process_signal(_signal_for(p), _bar_for(p))
    except Exception as e:  # noqa: BLE001
        return {"action": "failed", "error": str(e)}


@router.post("/scan")
async def advice_scan(body: AdviceScanRequest | None = None, _bot=Depends(get_bot_started)):
    advisor = get_advisor()
    created = advisor.scan(_parse_bars(body.bars if body is not None and body.bars else {}))
    return {"created": len(created), "proposals": [p.summary() for p in created]}


@router.get("/proposals")
async def list_proposals(status: str | None = None):
    advisor = get_advisor()
    advisor.expire_old()
    ps = advisor.all_proposals()
    if status:
        ps = [p for p in ps if p.status.value == status]
    return [p.summary() for p in ps]


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    p = get_advisor().get(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return p.summary()


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, bot=Depends(get_bot_started)):
    advisor = get_advisor()
    result = advisor.approve(proposal_id, run=False)
    if result.get("status") == "missing":
        raise HTTPException(status_code=404, detail="proposal not found")
    if result.get("approved"):
        p = advisor.get(proposal_id)
        result["execution"] = await _execute(p, bot)
    return result


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_proposal(proposal_id: str):
    result = get_advisor().reject(proposal_id)
    return result


@router.post("/reconcile")
async def reconcile():
    advisor = get_advisor()
    n = advisor.expire_old()
    return {"expired": n, "pending": len(advisor.pending())}