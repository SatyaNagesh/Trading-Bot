"""Discord paper-notification leg — fail-closed, never blocks the paper engine.

This module gives the TradingView → paper pipeline an OPTIONAL Discord
notification transport. It intentionally:

  * reads the bot BOT_TOKEN and the fixed configured CHANNEL_ID **only** from
    the environment (``QUANTLAB_DISCORD_BOT_TOKEN``,
    ``QUANTLAB_DISCORD_CHANNEL_ID``, gated by ``QUANTLAB_DISCORD_ENABLED``) —
    never from source, never from git, never from the caller;
  * uses the Discord **Bot HTTP (REST) API** transport:

        POST https://discord.com/api/v10/channels/{QUANTLAB_DISCORD_CHANNEL_ID}/messages
        Authorization: Bot {QUANTLAB_DISCORD_BOT_TOKEN}
        Content-Type:  application/json

    NOT webhooks. The channel is always ``QUANTLAB_DISCORD_CHANNEL_ID`` (an
    operator-fixed, non-secret channel ID) — a caller can never override it;
    the token is always ``QUANTLAB_DISCORD_BOT_TOKEN`` — a caller can never
    supply it and it is never read-echoed anywhere;
  * fails CLOSED: with the feature disabled, the token missing/blank, or the
    channel ID missing/blank the notifier is a harmless no-op (returns
    ``NOT_CONFIGURED`` from ``notify``, makes NO HTTP request) and the paper
    engine continues completely untouched;
  * never raises out of ``notify`` — any transport error is logged and
    swallowed so the paper loop is never delayed by notification trouble;
  * never touches order execution / risk / broker paths: it only *reports*
    what already happened on the paper path. It can never place, fill, or
    modify an order.

The previous **webhook** transport (``QUANTLAB_DISCORD_WEBHOOK_URL``) is
retained byte-identical in this module as the *legacy rollback leg*: unused by
the production path, kept so the deployment can roll back to the exact prior
behavior without a code change. It is removed only after the bot transport is
proven in the deployed environment.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from packages.core.logging import get_logger

logger = get_logger("discord_notify")

# Canonical env NAMES (never echoed, never committed, never from source).
ENV_DISCORD_ENABLED = "QUANTLAB_DISCORD_ENABLED"
ENV_DISCORD_BOT_TOKEN = "QUANTLAB_DISCORD_BOT_TOKEN"
ENV_DISCORD_CHANNEL_ID = "QUANTLAB_DISCORD_CHANNEL_ID"

# LEGACY (retained, unused by the production path — rollback leg).
ENV_DISCORD_WEBHOOK_URL = "QUANTLAB_DISCORD_WEBHOOK_URL"

DISCORD_API_BASE = "https://discord.com/api/v10"

_MAX_RETRIES = 2
_BACKOFF_SECONDS = 1.0
_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "QuantLab-Paper/0.1"
_TRUTHY = {"1", "true", "yes", "on"}


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


class DiscordNotifier:
    """Fail-closed Discord **Bot REST** notifier for paper-path events.

    Reads ``QUANTLAB_DISCORD_ENABLED`` + ``QUANTLAB_DISCORD_BOT_TOKEN`` +
    ``QUANTLAB_DISCORD_CHANNEL_ID`` from the environment. If the feature is
    disabled, the token missing/blank, or the channel ID missing/blank the
    notifier is DISABLED: ``notify`` returns ``NOT_CONFIGURED`` and the
    caller (the paper engine) is completely unaffected.
    """

    def __init__(
        self,
        *,
        enabled_flag: bool = False,
        bot_token: str = "",
        channel_id: str = "",
    ) -> None:
        self._channel_id = (str(channel_id).strip() if channel_id else "").strip()
        self._bot_token = (bot_token or "").strip()
        self._enabled_flag = enabled_flag and bool(self._bot_token) and bool(self._channel_id)
        self._client: httpx.AsyncClient | None = None
        self._send_count = 0
        self._last_status_code: int | None = None

    @classmethod
    def from_env(cls) -> "DiscordNotifier":
        """Build from canonical env NAMES (env only); fail-closed.

        Never echoes any value. Missing/blank token or channel => DISABLED.
        """
        return cls(
            enabled_flag=_env_truthy(ENV_DISCORD_ENABLED),
            bot_token=os.environ.get(ENV_DISCORD_BOT_TOKEN, ""),
            channel_id=os.environ.get(ENV_DISCORD_CHANNEL_ID, ""),
        )

    @property
    def enabled(self) -> bool:
        return self._enabled_flag

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

        Returns a status dict (NOT_CONFIGURED / SENT / DELIVERY_FAILED) so
        callers (and the honesty journal) can tell exactly what happened.
        """
        if not self.enabled:
            return {"status": "NOT_CONFIGURED", "sent": False, "status_code": None}

        payload = self._build_payload(symbol, direction, action, reason, event_id, meta)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bot {self._bot_token}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

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

        logger.error(
            "discord_notify_failed",
            symbol=symbol, error=last_exc, status_code=status_code,
        )
        return {
            "status": "DELIVERY_FAILED",
            "sent": False,
            "status_code": status_code,
            "error": last_exc,
            "attempts": 1 + _MAX_RETRIES,
        }

    async def _post(self, body: bytes, headers: dict[str, str]) -> int:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
        url = f"{DISCORD_API_BASE}/channels/{self._channel_id}/messages"
        resp = await self._client.post(url, content=body, headers=headers)
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
            "env_enabled": ENV_DISCORD_ENABLED,
            "env_token": ENV_DISCORD_BOT_TOKEN,
            "env_channel": ENV_DISCORD_CHANNEL_ID,
            "legacy_env_webhook": ENV_DISCORD_WEBHOOK_URL,
            "transport": "discord_bot-http-bot-api",
        }


class _LegacyWebhookLeg:
    """RETENTION-ONLY legacy webhook transport (rollback).

    Byte-preserved from the previous webhook transport. **Unused** by the
    production path: nothing references this class. It exists so operators can
    roll back to the exact old ``QUANTLAB_DISCORD_WEBHOOK_URL`` webhook
    behavior with no production code change. Remove only after the bot
    transport is proven in the deployed environment.
    """

    _ENV_LEGACY_WEBHOOK_URL = ENV_DISCORD_WEBHOOK_URL
    _MAX_RETRIES = 2
    _BACKOFF_SECONDS = 1.0
    _TIMEOUT_SECONDS = 8.0

    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = (webhook_url or "").strip()
        self._client: httpx.AsyncClient | None = None
        self._send_count = 0
        self._last_status_code: int | None = None

    @classmethod
    def from_env(cls) -> "_LegacyWebhookLeg":
        """Build from the LEGACY env NAME only; never echoes value; rollback."""
        return cls(os.environ.get(cls._ENV_LEGACY_WEBHOOK_URL, ""))

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
        """Legacy webhook behavior — fail-closed, never raises, retail-only."""
        if not self.enabled:
            return {"status": "NOT_CONFIGURED", "sent": False, "status_code": None}
        payload = self._build_payload(symbol, direction, action, reason, event_id, meta)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "QuantLab-Paper/0.1"}
        last_exc: str | None = None
        status_code: int | None = None
        for attempt in range(1 + self._MAX_RETRIES):
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
            if attempt < self._MAX_RETRIES:
                await asyncio.sleep(self._BACKOFF_SECONDS)
        logger.error(
            "legacy_webhook_notify_failed",
            symbol=symbol, error=last_exc, status_code=status_code,
        )
        return {
            "status": "DELIVERY_FAILED",
            "sent": False,
            "status_code": status_code,
            "error": last_exc,
            "attempts": 1 + self._MAX_RETRIES,
        }

    async def _post(self, body: bytes, headers: dict[str, str]) -> int:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._TIMEOUT_SECONDS)
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
            "env_webhook_url": self._ENV_LEGACY_WEBHOOK_URL,
            "transport": "webhook-legacy-retained",
        }
