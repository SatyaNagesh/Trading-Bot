"""SYNTHETIC TRADINGVIEW → PAPER INTEGRATION TEST.

These tests are synthetic market events exercising the real webhook -> validation
-> strategy/risk -> execution -> PaperBroker -> portfolio -> journal path. They
are NOT real market trades and must never be reported as such.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from packages.broker.gateway import BaseBroker, BrokerConfig, PaperBroker
from packages.core.exceptions import BrokerError
from packages.domain.models import Order, OrderStatus
from packages.session.manager import SessionManager, SessionStatus
from packages.trading.loop import PaperTradingLoop
from packages.webhook.tradingview import (
    SECRET_BODY_FIELD,
    SECRET_HEADER,
    WebhookSettings,
    TradingViewEventGateway,
)

from services.api import dependencies as api_deps
from services.api.main import create_app
from services.api.router_webhook import _reset_gateway


class _OpenSession(SessionManager):
    def is_open(self, dt=None):
        return True

    def check_session(self, dt=None):
        return SessionStatus.OPEN


class _ClosedSession(SessionManager):
    def is_open(self, dt=None):
        return False

    def check_session(self, dt=None):
        return SessionStatus.WEEKEND


class _FakeLiveBroker(BaseBroker):
    """A live-capable broker that records calls — must NEVER be reached."""

    live_capable = True
    calls = []

    async def place_order(self, order: Order) -> OrderStatus:
        self.calls.append(order.id)
        return OrderStatus.FILLED

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_positions(self) -> list[dict]:
        return []

    async def get_account(self) -> dict:
        return {"mode": "fake-live"}

    async def get_historical_data(self, symbol, start, end):
        return []


class _BrokenBroker(PaperBroker):
    async def place_order(self, order: Order) -> OrderStatus:
        raise BrokerError("paper broker unavailable")


def _inject(bot, *, session=_OpenSession(), broker=None):
    """Point the bot's loop at a controlled session/paper broker for determinism."""
    b = broker or PaperBroker(BrokerConfig(mode="paper"))
    bot.loop.session = session
    bot.loop.broker = b
    bot.loop.execution.broker = b


def _valid_event(**overrides) -> dict:
    event = {
        SECRET_BODY_FIELD: "test-secret",
        "event_id": "evt-0001",
        "symbol": "NSE:RELIANCE",
        "timeframe": "1h",
        "direction": "long",
        "timestamp": datetime.now(timezone := UTC).isoformat(),  # noqa: F841
        "price": 2950.0,
        "source": "tradingview",
    }
    event.update(overrides)
    return event


def _gateway(tmp_path, loop, *, secret="test-secret", symbols=("RELIANCE.NS", "NOPRICE.NS", "24_7.NS")):
    settings = WebhookSettings(
        secret=secret,
        known_symbols=symbols,
        ledger_dir=str(tmp_path),
        symbols_24_7=frozenset({"24_7.NS"}),
    )
    return TradingViewEventGateway(settings=settings, loop=loop)


class TestGatewayPaperPath:
    async def test_valid_long_event_fills_paper_order(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event())
        assert rec["status"] == "FILLED"
        assert rec["event_id"] == "evt-0001"
        pos = loop.portfolio.get_position("RELIANCE.NS")
        assert pos is not None and pos.quantity > 0

    async def test_round_trip_updates_journal_and_pnl(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        await gw.handle(_valid_event(event_id="entry", price=100.0))
        rec = await gw.handle(_valid_event(event_id="exit", direction="short", price=110.0))
        assert rec["status"] == "FILLED"
        assert loop.journal.total_entries() >= 1
        assert loop.portfolio.portfolio.realized_pnl > 0
        assert loop.portfolio.verify_integrity()["verified"] is True

    async def test_same_event_id_only_accepted_once(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        first = await gw.handle(_valid_event(event_id="evt-dup"))
        assert first["status"] == "FILLED"
        second = await gw.handle(_valid_event(event_id="evt-dup"))
        assert second["status"] == "DUPLICATE"
        assert len(loop.oms.get_all_orders()) == 1

    async def test_duplicate_survives_restart_via_ledger(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw1 = _gateway(tmp_path, loop)
        assert (await gw1.handle(_valid_event(event_id="evt-restart")))["status"] == "FILLED"
        gw2 = _gateway(tmp_path, loop)
        rec = await gw2.handle(_valid_event(event_id="evt-restart"))
        assert rec["status"] == "DUPLICATE"

    async def test_neutral_direction_creates_no_order(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(direction="neutral"))
        assert rec["status"] == "NEUTRAL"
        assert len(loop.oms.get_all_orders()) == 0

    async def test_missing_price_rejected_no_dirge(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        payload = _valid_event(event_id="evt-noprice")
        payload.pop("price")
        rec = await gw.handle(payload)
        assert rec["status"] == "NO_PRICE"
        assert len(loop.oms.get_all_orders()) == 0


class TestGatewayValidation:
    async def test_wrong_secret_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(secret="wrong"), "wrong")
        assert rec["status"] == "UNAUTHENTICATED"

    async def test_missing_secret_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        payload = _valid_event()
        payload.pop(SECRET_BODY_FIELD)
        rec = await gw.handle(payload)
        assert rec["status"] == "UNAUTHENTICATED"

    async def test_secret_via_header_accepted(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        payload = _valid_event(event_id="evt-hdr")
        payload.pop(SECRET_BODY_FIELD)
        rec = await gw.handle(payload, "test-secret")
        assert rec["status"] == "FILLED"

    async def test_malformed_payload_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        assert (await gw.handle("not-a-dict", "test-secret"))["status"] == "MALFORMED"
        payload = _valid_event()
        payload.pop("symbol")
        assert (await gw.handle(payload, "test-secret"))["status"] == "MALFORMED"
        assert (await gw.handle(_valid_event(direction="banana"), "test-secret"))["status"] == "MALFORMED"

    async def test_wrong_source_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        assert (await gw.handle(_valid_event(source="metatrader"), "test-secret"))["status"] == "FORBIDDEN_SOURCE"

    async def test_stale_event_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        rec = await gw.handle(_valid_event(timestamp=ts), "test-secret")
        assert rec["status"] == "STALE"

    async def test_future_event_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        ts = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        rec = await gw.handle(_valid_event(timestamp=ts), "test-secret")
        assert rec["status"] == "FUTURE"

    async def test_unknown_symbol_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(symbol="NSE:NOTREAL"), "test-secret")
        assert rec["status"] == "UNKNOWN_SYMBOL"

    async def test_invalid_timeframe_rejected(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(timeframe="4x"), "test-secret")
        assert rec["status"] == "INVALID_TIMEFRAME"


class TestSessionHandle:
    async def test_closed_session_rejected_outside_session(self, tmp_path):
        loop = PaperTradingLoop(session_manager=_ClosedSession())  # instrument session CLOSED
        gw = _gateway(tmp_path, loop)
        now = datetime.now(UTC)
        rec = await gw.handle(_valid_event(event_id="evt-closed", timestamp=now.isoformat()), "test-secret")
        assert rec["status"] == "REJECTED_OUTSIDE_SESSION"
        assert rec.get("session_status") == "weekend"
        assert len(loop.oms.get_all_orders()) == 0
        assert loop.portfolio.get_position("RELIANCE.NS") is None  # no phantom trade

    async def test_24_7_symbol_bypasses_session_gate(self, tmp_path):
        loop = PaperTradingLoop(session_manager=_ClosedSession())  # session closed...
        gw = _gateway(tmp_path, loop, symbols=("24_7.NS",))
        now = datetime.now(UTC)
        rec = await gw.handle(_valid_event(symbol="24_7.NS", event_id="evt-247", timestamp=now.isoformat()), "test-secret")
        assert rec["status"] == "FILLED"  # ...but crypto configured 24/7 bypasses the gate
        assert loop.portfolio.get_position("24_7.NS") is not None


class TestRiskAndKillSwitch:
    async def test_kill_switch_rejects_order(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        loop.risk.kill_switch(True)
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(event_id="evt-ks"), "test-secret")
        assert rec["status"] == "REJECTED_BY_RISK"
        assert loop.portfolio.get_position("RELIANCE.NS") is None

    async def test_risk_limit_rejects(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        loop.risk.budget.max_concurrent_trades = 0
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(event_id="evt-risk"), "test-secret")
        assert rec["status"] == "REJECTED_BY_RISK"


class TestFailureModes:
    async def test_broker_unavailable_fails_closed(self, tmp_path):
        loop = PaperTradingLoop(broker=_BrokenBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(event_id="evt-broken"), "test-secret")
        assert rec["status"] == "FAILED"
        assert loop.portfolio.get_position("RELIANCE.NS") is None

    async def test_ledger_unavailable_does_not_hang_or_double_order(self, tmp_path):
        pid = tmp_path / "blocker"
        pid.mkdir()
        ledger_file = pid / "file"
        ledger_file.write_text("x")
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop, symbols=("RELIANCE.NS",))
        gw._ledger = ledger_file / "events.jsonl"  # mkdir under a FILE -> OSError
        rec = await gw.handle(_valid_event(event_id="evt-ldb"), "test-secret")
        assert rec["status"] in ("FILLED", "MALFORMED", "UNAUTHENTICATED")  # no crash

    async def test_disabled_webhook_without_secret(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop, secret="")
        rec = await gw.handle(_valid_event())
        assert rec["status"] == "NOT_CONFIGURED"

    async def test_webhook_replay_is_duplicate(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        gw = _gateway(tmp_path, loop)
        await gw.handle(_valid_event(event_id="evt-replay"), "test-secret")
        rec = await gw.handle(_valid_event(event_id="evt-replay"), "test-secret")
        assert rec["status"] == "DUPLICATE"


class TestPaperLiveIsolation:
    async def test_live_capable_broker_never_reached(self, tmp_path):
        loop = PaperTradingLoop(broker=PaperBroker(BrokerConfig(mode="paper")), session_manager=_OpenSession())
        fake = _FakeLiveBroker(BrokerConfig(mode="paper"))
        loop.broker = fake
        loop.execution.broker = fake
        gw = _gateway(tmp_path, loop)
        rec = await gw.handle(_valid_event(event_id="evt-live"), "test-secret")
        assert rec["status"] == "PAPER_GUARD"
        assert fake.calls == []  # webhook refused before any order reached the broker
        assert len(loop.oms.get_all_orders()) == 0


# ── API-level integration (FastAPI TestClient) ──────────────────────────────

class TestWebhookAPI:
    def _client(self, monkeypatch, tmp_path):
        monkeypatch.setenv("QUANTLAB_WEBHOOK_SECRET", "api-secret")
        monkeypatch.setenv("QUANTLAB_WEBHOOK_LEDGER_DIR", str(tmp_path))
        _reset_gateway()
        app = create_app()
        return TestClient(app)

    def test_paper_guard_over_http_returns_503(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            fake = _FakeLiveBroker(BrokerConfig(mode="paper"))
            bot.loop.broker = fake
            bot.loop.execution.broker = fake
            r = client.post(
                "/webhook/tradingview",
                headers={SECRET_HEADER: "api-secret"},
                json={"symbol": "RELIANCE", "timeframe": "1h", "direction": "long",
                      "timestamp": datetime.now(UTC).isoformat(), "price": 2950.0,
                      "source": "tradingview"},
            )
            assert r.status_code == 503
            assert r.json()["status"] == "PAPER_GUARD"
            assert fake.calls == []

    def test_http_full_paper_round_trip(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            _inject(bot)
            payload = {
                "event_id": "http-1",
                "symbol": "NSE:RELIANCE",
                "timeframe": "1h",
                "direction": "long",
                "timestamp": datetime.now(UTC).isoformat(),
                "price": 100.0,
                "source": "tradingview",
            }
            r1 = client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload)
            assert r1.status_code == 200
            assert r1.json()["status"] == "FILLED"
            order_id = r1.json().get("order_id")
            assert order_id

            r2 = client.post(
                "/webhook/tradingview",
                headers={SECRET_HEADER: "api-secret"},
                json={**payload, "event_id": "http-2", "direction": "short", "price": 120.0},
            )
            assert r2.status_code == 200
            assert r2.json()["status"] == "FILLED"

            pf = bot.loop.portfolio
            assert pf.get_position("RELIANCE.NS") is not None
            assert pf.portfolio.realized_pnl > 0
            assert bot.loop.journal.total_entries() >= 1
            assert pf.verify_integrity()["verified"] is True

    def test_http_duplicate_returns_duplicate(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            _inject(bot)
            payload = {
                "event_id": "http-dup",
                "symbol": "NSE:RELIANCE",
                "timeframe": "1h",
                "direction": "long",
                "timestamp": datetime.now(UTC).isoformat(),
                "price": 200.0,
                "source": "tradingview",
            }
            assert client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload).status_code == 200
            r = client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload)
            assert r.status_code == 200
            assert r.json()["status"] == "DUPLICATE"

    def test_http_bad_secret_401(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            payload = _valid_event()
            payload[SECRET_BODY_FIELD] = "wrong"
            r = client.post("/webhook/tradingview", json=payload)
            assert r.status_code == 401
            assert r.json()["status"] == "UNAUTHENTICATED"

    def test_http_malformed_400(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            r = client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json={"source": "tradingview"})
            assert r.status_code == 400
            assert r.json()["status"] == "MALFORMED"

    def test_http_closed_session_no_phantom_trade(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            _inject(bot, session=_ClosedSession())
            payload = {
                "event_id": "http-closed",
                "symbol": "NSE:RELIANCE",
                "timeframe": "1h",
                "direction": "long",
                "timestamp": datetime.now(UTC).isoformat(),
                "price": 100.0,
                "source": "tradingview",
            }
            r = client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload)
            assert r.status_code == 200
            assert r.json()["status"] == "REJECTED_OUTSIDE_SESSION"
            assert bot.loop.portfolio.get_position("RELIANCE.NS") is None

    def test_http_observability_endpoints(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            _inject(bot)
            payload = {
                "event_id": "http-obs",
                "symbol": "NSE:RELIANCE",
                "timeframe": "1h",
                "direction": "long",
                "timestamp": datetime.now(UTC).isoformat(),
                "price": 150.0,
                "source": "tradingview",
            }
            assert client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload).status_code == 200
            events = client.get("/webhook/events").json()
            assert any(e["event_id"] == "http-obs" for e in events)
            status = client.get("/webhook/status").json()
            assert status["counts"].get("FILLED", 0) >= 1
            assert status["last_event"]["event_id"] == "http-obs"
            assert "session" in status

    def test_http_kill_switch_rejects(self, monkeypatch, tmp_path):
        client = self._client(monkeypatch, tmp_path)
        with client:
            bot = api_deps.get_bot_instance()
            _inject(bot)
            bot.loop.risk.kill_switch(True)
            payload = {
                "event_id": "http-ks",
                "symbol": "NSE:RELIANCE",
                "timeframe": "1h",
                "direction": "long",
                "timestamp": datetime.now(UTC).isoformat(),
                "price": 100.0,
                "source": "tradingview",
            }
            r = client.post("/webhook/tradingview", headers={SECRET_HEADER: "api-secret"}, json=payload)
            assert r.status_code == 200
            assert r.json()["status"] == "REJECTED_BY_RISK"
            assert bot.loop.portfolio.get_position("RELIANCE.NS") is None