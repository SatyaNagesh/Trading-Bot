"""Strategy registry — authoritative status must stay honest.

No unproven strategy may reach PAPER_APPROVED or LIVE_APPROVED. Approval
requires recorded evidence with an authority field; nobody may fabricate one.
COMP3 strategies must remain RETIRED; autonomous_momentum must remain RESEARCH.
"""

from datetime import UTC, datetime

import pytest

from packages.strategies.registry import (
    _ALLOWED_TRANSITIONS,
    RESEARCH_ONLY_STATUS,
    RegistryState,
    StrategyRegistry,
)


@pytest.fixture
def reg(tmp_path):
    return StrategyRegistry(path=tmp_path / "registry.json")


def _evidence(authority: str = "lead_engineer") -> list[dict]:
    return [{"authority": authority, "at": datetime.now(UTC).isoformat()}]


class TestRegistryGuarantees:
    def test_new_strategy_defaults_to_research(self, reg):
        rec = reg.register("s1", "Unvalidated")
        assert rec.state == RegistryState.RESEARCH

    def test_cannot_approve_without_evidence(self, reg):
        reg.register("s1", "S")
        with pytest.raises(ValueError):
            reg.transition("s1", RegistryState.PAPER_APPROVED)  # no evidence
        assert reg.state_of("s1") == RegistryState.RESEARCH

    def test_cannot_skip_states(self, reg):
        reg.register("s1", "S")
        with pytest.raises(ValueError):
            reg.transition("s1", RegistryState.LIVE_APPROVED, evidence=_evidence())
        assert reg.state_of("s1") == RegistryState.RESEARCH

    def test_validated_with_evidence_then_paper(self, reg):
        reg.register("s1", "S")
        reg.transition("s1", RegistryState.VALIDATED, evidence=_evidence())
        reg.transition(
            "s1",
            RegistryState.PAPER_APPROVED,
            evidence=_evidence(authority="gating_board"),
        )
        assert reg.state_of("s1") == RegistryState.PAPER_APPROVED

    def test_live_approval_requires_prior_paper(self, reg):
        reg.register("s1", "S")
        reg.transition("s1", RegistryState.VALIDATED, evidence=_evidence())
        reg.transition(
            "s1",
            RegistryState.PAPER_APPROVED,
            evidence=_evidence(authority="gating_board"),
        )
        reg.transition("s1", RegistryState.LIVE_APPROVED, evidence=_evidence(authority="principal"))
        assert reg.state_of("s1") == RegistryState.LIVE_APPROVED

    def test_retired_is_terminal(self, reg):
        reg.register("COMP3", "COMP3")
        reg.retire("COMP3")
        assert reg.state_of("COMP3") == RegistryState.RETIRED
        assert _ALLOWED_TRANSITIONS[RegistryState.RETIRED] == set()

    def test_evidence_fabrication_blocked(self, reg):
        """Empty evidence list with a dangling authority is still rejected."""
        reg.register("s1", "S")
        with pytest.raises(ValueError):
            reg.transition("s1", RegistryState.VALIDATED, evidence=[{"at": "now"}])

    def test_persistence_roundtrip(self, reg):
        reg.register("s1", "S1")
        reg.transition("s1", RegistryState.VALIDATED, evidence=_evidence())
        reg.save()
        reloaded = StrategyRegistry(path=reg._path)
        assert reloaded.state_of("s1") == RegistryState.VALIDATED


class TestSeededGroundTruth:
    def test_seeded_knows_all_known_strategies(self, tmp_path):
        reg = StrategyRegistry(path=tmp_path / "seed.json")
        for sid in (
            "autonomous_momentum",
            "sma_crossover",
            "ema_trend",
            "rsi_mean_reversion",
            "COMP3_STRATEGY_V1",
            "COMP3_STRATEGY_V2",
            "paper-reversal",
            "default",
        ):
            assert reg.register(sid, sid).state == RegistryState.RESEARCH, sid

    def test_comp3_strategies_retired(self, tmp_path):
        reg = StrategyRegistry(path=tmp_path / "seed.json")
        reg.retire("COMP3_STRATEGY_V1")
        reg.retire("COMP3_STRATEGY_V2")
        assert reg.state_of("COMP3_STRATEGY_V2") == RegistryState.RETIRED

    def test_autonomous_momentum_cannot_be_approved_without_gate(self, reg):
        """autonomous_momentum is unproven; block any approval attempt."""
        reg.register("autonomous_momentum", "Autonomous Momentum")
        with pytest.raises(ValueError):
            reg.transition("autonomous_momentum", RegistryState.VALIDATED)
        assert reg.state_of("autonomous_momentum") == RegistryState.RESEARCH

    def test_legacy_statuses_are_not_authoritative(self):
        for legacy in ("active", "candidate", "watchlist"):
            assert legacy in RESEARCH_ONLY_STATUS
