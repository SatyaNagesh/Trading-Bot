"""Mock-only contract tests for the migrated Discord **Bot HTTP** notifier.

No real Discord request is ever made: every HTTP interaction is served by an
in-process ``httpx.MockTransport``. The bot token VALUE used here is a fake
test literal; tests assert only name-level (never real-secret) constract.

Gates proved (each ties to a production guarantee in
``packages/notifications/discord.py``):

  * transport  -> POST {DISCORD_API_BASE}/channels/{CHANNEL_ID}/messages,
                  headers ``Authorization: Bot <token>`` (Bot prefix; the URL
                  never carries a webhook or a token);
  * fail-closed -> disabled/blank-token/blank-channel => NOT_CONFIGURED,
                   zero HTTP attempts;
  * never-raises -> a broken/503 transport => DELIVERY_FAILED, notify() never
                    propagates an exception;
  * bounded    -> non-2xx retried at most 1+_MAX_RETRIES, then DELIVERY_FAILED;
  * privacy    -> the token VALUE never appears in the returned record, in
                  stats(), or in any error/status string.
"""

import json

import httpx
import pytest

from packages.notifications.discord import (
    _MAX_RETRIES,
    ENV_DISCORD_BOT_TOKEN,
    ENV_DISCORD_CHANNEL_ID,
    ENV_DISCORD_ENABLED,
    DiscordNotifier,
)

FAKE_TOKEN = "test-only-fake-bot-token-2c9f-not-a-secret"
FAKE_CHANNEL = "850012345678901234"


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://discord.com",
    )


def _sentry(record: dict) -> str:
    return json.dumps(record)


class TestBotTransportContract:
    async def test_posts_to_exact_bot_endpoint_with_bot_auth(self):
        calls = []

        async def handler(request):
            calls.append(request)
            assert request.method == "POST"
            assert request.url.path == f"/api/v10/channels/{FAKE_CHANNEL}/messages"
            assert request.headers["Authorization"] == f"Bot {FAKE_TOKEN}"
            assert FAKE_TOKEN not in request.url.path
            return httpx.Response(200, json={"id": "mock-msg-1"})

        n = DiscordNotifier(enabled_flag=True, bot_token=FAKE_TOKEN, channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        rec = await n.notify(
            symbol="NSE:RELIANCE",
            direction="long",
            action="FILLED",
            reason="paper entry signal",
            event_id="evt-0001",
            meta={"timeframe": "1h", "alert_price": "2950.0"},
        )
        assert rec["status"] == "SENT"
        assert rec["sent"] is True
        assert len(calls) == 1
        assert FAKE_TOKEN not in _sentry(rec)

    async def test_not_config_from_blank_token_makes_no_request(self):
        def handler(request):
            pytest.fail("must not be called")

        n = DiscordNotifier(enabled_flag=True, bot_token="", channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        assert n.enabled is False
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert rec["status"] == "NOT_CONFIGURED"
        assert rec["sent"] is False

    async def test_not_config_from_blank_channel_makes_no_request(self):
        def handler(request):
            pytest.fail("must not be called")

        n = DiscordNotifier(enabled_flag=True, bot_token=FAKE_TOKEN, channel_id="")
        n._client = _mock_client(handler)
        assert n.enabled is False
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert rec["status"] == "NOT_CONFIGURED"

    async def test_not_config_from_disabled_flag_makes_no_request(self):
        def handler(request):
            pytest.fail("must not be called")

        n = DiscordNotifier(enabled_flag=False, bot_token=FAKE_TOKEN, channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        assert n.enabled is False
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert rec["status"] == "NOT_CONFIGURED"

    async def test_bounded_retries_then_delivery_failed(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503)

        n = DiscordNotifier(enabled_flag=True, bot_token=FAKE_TOKEN, channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert rec["status"] == "DELIVERY_FAILED"
        assert rec["sent"] is False
        assert len(calls) == 1 + _MAX_RETRIES

    async def test_never_raises_on_broken_transport(self):
        calls = []

        def handler(request):
            calls.append(request)
            raise httpx.TransportError("boom")

        n = DiscordNotifier(enabled_flag=True, bot_token=FAKE_TOKEN, channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert rec["status"] == "DELIVERY_FAILED"
        assert len(calls) == 1 + _MAX_RETRIES

    async def test_token_value_never_leaks_into_record_or_stats(self):
        def handler(request):
            return httpx.Response(200, json={"id": "mock-no-leak"})

        n = DiscordNotifier(enabled_flag=True, bot_token=FAKE_TOKEN, channel_id=FAKE_CHANNEL)
        n._client = _mock_client(handler)
        rec = await n.notify(symbol="X", direction="long", action="FILLED", reason="r")
        assert FAKE_TOKEN not in _sentry(rec)
        assert FAKE_TOKEN not in _sentry(n.stats())


class TestEnvSurface:
    async def test_from_env_builds_from_canonical_names(self, monkeypatch):
        monkeypatch.setenv(ENV_DISCORD_ENABLED, "1")
        monkeypatch.setenv(ENV_DISCORD_BOT_TOKEN, FAKE_TOKEN)
        monkeypatch.setenv(ENV_DISCORD_CHANNEL_ID, FAKE_CHANNEL)
        n = DiscordNotifier.from_env()
        assert n.enabled is True
        assert n.stats()["env_enabled"] == ENV_DISCORD_ENABLED
        assert n.stats()["env_token"] == ENV_DISCORD_BOT_TOKEN
        assert n.stats()["env_channel"] == ENV_DISCORD_CHANNEL_ID

    async def test_from_env_blank_token_is_disabled(self, monkeypatch):
        monkeypatch.setenv(ENV_DISCORD_ENABLED, "1")
        monkeypatch.setenv(ENV_DISCORD_BOT_TOKEN, "")
        monkeypatch.setenv(ENV_DISCORD_CHANNEL_ID, FAKE_CHANNEL)
        assert DiscordNotifier.from_env().enabled is False
