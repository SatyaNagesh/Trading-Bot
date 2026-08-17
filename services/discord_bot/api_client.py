"""API client — calls the QuantLab API via httpx."""

from typing import Any

import httpx


class QuantLabAPIClient:
    """Thin HTTP client that wraps the QuantLab REST API.

    All methods delegate to the API — no direct engine imports.
    """

    def __init__(self, base_url: str, api_secret: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_secret}"}
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _get(self, path: str) -> Any:
        r = httpx.get(self._url(path), headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, **kwargs) -> Any:
        r = httpx.post(self._url(path), headers=self._headers, json=kwargs.get("json"), timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    # ── Health ──
    def health(self) -> dict[str, str]:
        return self._get("/health")

    def ready(self) -> dict[str, Any]:
        return self._get("/ready")

    # ── Trading ──
    def trading_status(self) -> dict[str, Any]:
        return self._get("/trading/status")

    def trading_start(self) -> dict[str, str]:
        return self._post("/trading/start")

    def trading_stop(self, reason: str = "Discord command") -> dict[str, str]:
        return self._post("/trading/stop", json={"reason": reason})

    # ── Portfolio ──
    def portfolio_summary(self) -> dict[str, Any]:
        return self._get("/portfolio/summary")

    def portfolio_positions(self) -> list[dict[str, Any]]:
        return self._get("/portfolio/positions")

    def portfolio_trades(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._get(f"/portfolio/trades?limit={limit}")

    # ── Orders ──
    def order_counts(self) -> dict[str, Any]:
        return self._get("/orders/counts")

    def open_orders(self) -> list[dict[str, Any]]:
        return self._get("/orders/open")

    # ── Risk ──
    def risk_summary(self) -> dict[str, Any]:
        return self._get("/risk/summary")

    # ── Strategies ──
    def list_strategies(self) -> list[dict[str, Any]]:
        return self._get("/strategies/")

    def strategy_rankings(self, top_n: int = 5) -> list[dict[str, Any]]:
        return self._get(f"/strategies/candidates/rankings?top_n={top_n}")

    # ── Alerts ──
    def alert_counts(self) -> dict[str, Any]:
        return self._get("/alerts/counts")

    # ── System ──
    def metrics(self) -> dict[str, Any]:
        return self._get("/system/metrics")

    def dashboard(self) -> dict[str, str]:
        return self._get("/system/dashboard")

    # ── Advice (human-in-the-loop proposals) ──
    def advice_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        q = f"?status={status}" if status else ""
        return self._get(f"/advice/proposals{q}")

    def advice_approve(self, proposal_id: str) -> dict[str, Any]:
        return self._post(f"/advice/proposals/{proposal_id}/approve")

    def advice_cancel(self, proposal_id: str) -> dict[str, Any]:
        return self._post(f"/advice/proposals/{proposal_id}/cancel")

    # ── Manual trade (call out a position on demand) ──
    def manual_trade(self, symbol: str, side: str = "long", price: float | None = None) -> dict[str, Any]:
        payload = {"symbol": symbol, "side": side}
        if price is not None:
            payload["price"] = price
        return self._post("/trading/manual", json=payload)
