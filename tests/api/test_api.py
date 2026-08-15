"""API integration tests — tests the FastAPI endpoints via TestClient."""

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "quantlab-api"

    def test_live(self, client):
        r = client.get("/live")
        assert r.status_code == 200
        assert r.json()["alive"] == "true"

    def test_ready(self, client):
        r = client.get("/ready")
        assert r.status_code == 200
        data = r.json()
        assert "ready" in data
        assert "database_accessible" in data


class TestTrading:
    def test_trading_status_default(self, client):
        r = client.get("/trading/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "cycle_count" in data

    def test_trading_start_stop(self, client):
        r = client.post("/trading/start")
        assert r.status_code == 200
        r = client.get("/trading/status")
        assert r.json()["running"] is True
        r = client.post("/trading/stop", json={"reason": "test"})
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"


class TestPortfolio:
    def test_portfolio_summary(self, client):
        r = client.get("/portfolio/summary")
        assert r.status_code == 200
        data = r.json()
        assert "initial_capital" in data

    def test_portfolio_positions(self, client):
        r = client.get("/portfolio/positions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_portfolio_trades(self, client):
        r = client.get("/portfolio/trades")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_portfolio_integrity(self, client):
        r = client.get("/portfolio/integrity")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestOrders:
    def test_order_counts(self, client):
        r = client.get("/orders/counts")
        assert r.status_code == 200
        data = r.json()
        assert "PENDING" in data

    def test_open_orders(self, client):
        r = client.get("/orders/open")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_orders(self, client):
        r = client.get("/orders/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_order(self, client):
        r = client.post(
            "/orders/",
            params={
                "strategy_id": "test_strat",
                "portfolio_id": "test_port",
                "symbol": "TEST",
                "side": "BUY",
                "quantity": 10,
                "order_type": "MARKET",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "order_id" in data


class TestRisk:
    def test_risk_summary(self, client):
        r = client.get("/risk/summary")
        assert r.status_code == 200
        data = r.json()
        assert "kill_switch_active" in data
        assert "max_drawdown" in data

    def test_kill_switch(self, client):
        r = client.post("/risk/kill-switch", params={"active": True})
        assert r.status_code == 200
        r = client.post("/risk/kill-switch", params={"active": False})
        assert r.status_code == 200

    def test_daily_loss(self, client):
        r = client.get("/risk/daily-loss")
        assert r.status_code == 200
        assert "daily_loss" in r.json()


class TestStrategies:
    def test_list_strategies(self, client):
        r = client.get("/strategies/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_rankings(self, client):
        r = client.get("/strategies/candidates/rankings")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_lifecycle(self, client):
        r = client.get("/strategies/lifecycle")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestAnalytics:
    def test_regime(self, client):
        r = client.get("/analytics/regime")
        assert r.status_code == 200
        assert "current_regime" in r.json()

    def test_health_monitor(self, client):
        r = client.get("/analytics/health-monitor")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)


class TestAlerts:
    def test_alert_counts(self, client):
        r = client.get("/alerts/counts")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_get_alerts(self, client):
        r = client.get("/alerts/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestProduction:
    def test_namespaces(self, client):
        r = client.get("/system/namespaces")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_metrics(self, client):
        r = client.get("/system/metrics")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_dashboard(self, client):
        r = client.get("/system/dashboard")
        assert r.status_code == 200
        assert "dashboard" in r.json()


class TestConfig:
    def test_get_config(self, client):
        r = client.get("/config/")
        assert r.status_code == 200
        data = r.json()
        assert "initial_capital" in data

    def test_risk_budget(self, client):
        r = client.get("/config/risk-budget")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
