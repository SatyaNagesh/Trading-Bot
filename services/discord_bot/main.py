"""QuantLab AI Discord Bot — API client, no direct engine imports.

Consumes the QuantLab REST API via httpx. Requires the API server to be running.
"""

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

import discord
from discord.ext import commands

from packages.core.logging import setup_logging, get_logger
from services.discord_bot.config import DiscordBotConfig
from services.discord_bot.api_client import QuantLabAPIClient
from services.discord_bot.commands import QuantLabCog
from services.discord_bot.advice_cog import AdviceCog

setup_logging()
logger = get_logger("discord_bot")


def main():
    cfg = DiscordBotConfig()

    if not cfg.token:
        logger.error("discord_token_missing", message="Set QUANTLAB_DISCORD_TOKEN in .env")
        return

    client = QuantLabAPIClient(base_url=cfg.api_base_url, api_secret=cfg.api_secret)

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix=cfg.command_prefix, intents=intents)

    @bot.event
    async def on_ready():
        logger.info("discord_bot_ready", user=str(bot.user))
        await bot.add_cog(QuantLabCog(bot, client))
        await bot.add_cog(AdviceCog(bot, client, cfg))
        await bot.tree.sync()

    bot.run(cfg.token)


if __name__ == "__main__":
    main()
