"""Discord paper-notification leg — fail-closed, never blocks the paper engine.

This module gives the TradingView → paper pipeline an OPTIONAL Discord
notification transport. It intentionally:

  * reads the webhook URL **only** from the environment
    (``QUANTLAB_DISCORD_WEBHOOK_URL``) — never from source, never from git;
  * fails CLOSED: with no URL configured the notifier is a harmless no-op
    (returns ``NOT_CONFIGURED``) and the paper engine continues untouched;
  * never raises out of ``notify`` — any transport error is logged and
    swallowed so the paper loop is never delayed by notification trouble;
  * never touches order execution / risk / broker paths: it only *reports*
    what already happened on the paper path.

This is a **paper-only** notification channel. It can never place, fill, or
modify an order. It is deliberately not wired to any live-capable broker leg.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from packages.core.logging import get_logger

logger = get_logger("discord_notify")

ENV_DISCORD_WEBHOOK_URL = "QUANTLAB_DISCORD_WEBHOOK_URL"

_MAX_RETRIES = 2
_BACKOFF_SECONDS = 1.0


class DiscordNotifier:
    """Fail-closed Discord webhook notifier for paper-path events.

    Reads ``QUANTLAB_DISCORD_WEBHOOK_URL`` from the environment. If unset or
    blank the notifier is DISABLED: ``notify`` returns ``NOT_CONFIGURED`` and
    the caller (the paper engine) is completely unaffected.
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = (webhook_url or "").strip()
        self._client: httpx.AsyncClient | None = None
        self._send_count = 0
        self._last_status_code: int | None = None

    @classmethod
    def from_env(cls) -> "DiscordNotifier":
        """Build from ``QUANTLAB_DISCORD_WEBHOOK_URL`` (env only); fail-closed.

        Never echoes the value. Unset/blank => DISABLED no-op notifier.
        """
        return cls(os.environ.get(ENV_DISCORD_WEBHOOK_URL, ""))

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    async def notify(
        self,
        *,
        symbol: str,
        direction: str,
        action: str,
        reason: str,
        event_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one bounded paper notification. Fail-closed; never raises.

        Returns a dict with status/config/status_code so callers (and the
        honesty journal) can tell exactly what happened.
        """
        if not self.enabled:
            return {"status": "NOT_CONFIGURED", "sent": False, "status_code": None}

        payload = self._build_payload(symbol, direction, action, reason, event_id, meta)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "QuantLab-Paper/0.1"}

        last_exc: str | None = None
        status_code: int | None = None
        for attempt in range(1 + _MAX_RETRIES):
            try:
                status_code = await self._post(body, headers)
                if status_code < 300:
                    self._send_count += 1
                    self._last_status_code = status_code
                    return {
                        "status": "SENT",
                        "sent": True,
                        "status_code": status_code,
                        "attempts": attempt + 1,
                    }
                last_exc = f"non-2xx status {status_code}"
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                last_exc = f"{type(e).__name__}: {e}"
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_SECONDS)

        logger.error("discord_notify_failed", symbol=symbol, error=last_exc, status=status_code)
        return {
            "status": "DELIVERY_FAILED",
            "sent": False,
            "status_code": status_code,
            "error": last_exc,
            "attempts": 1 + _MAX_RETRIES,
        }

    async def _post(self, body: bytes, headers: dict[str, str]) -> int:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=8.0)
        resp = await self._client.post(self.webhook_url, content=body, headers=headers)
        await resp.aread()
        return resp.status_code

    @staticmethod
    def _build_payload(
        symbol: str, direction: str, action: str, reason: str,
        event_id: str | None, meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        embed = {
            "title": f"QuantLab Paper {action.upper()}",
            "description": reason,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Direction", "value": direction, "inline": True},
                {"name": "Action", "value": action, "inline": True},
            ],
            "color": 0x1E8449 if action == "FILLED" else 0xA93226,
        }
        if event_id:
            embed["footer"] = {"text": f"event_id: {event_id}"}
        if meta:
            for k, v in list(meta.items())[:8]:
                embed["fields"].append({"name": str(k), "value": str(v), "inline": True})
        return {
            "content": "QuantLab **paper-only** notification",
            "embeds": [embed],
        }

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "send_count": self._send_count,
            "last_status_code": self._last_status_code,
            "env_name": ENV_DISCORD_WEBHOOK_URL,
        }
