"""Discord advisor cog — human-in-the-loop trade approvals via buttons."""

import asyncio
import time

from discord import Color, Embed, ButtonStyle, ui, app_commands
from discord.ext import commands, tasks

from services.discord_bot.api_client import QuantLabAPIClient
from services.discord_bot.config import DiscordBotConfig


def _proposal_embed(p: dict) -> Embed:
    embed = Embed(
        title=f"🔔 Trade opportunity — {p['symbol']} ({p.get('company_name', '')})",
        color=Color.green(),
    )
    embed.add_field(name="Company", value=p.get("company_name", "—"), inline=True)
    embed.add_field(name="Sector", value=p.get("sector", "—"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Strategy", value=p.get("strategy", "—"), inline=True)
    embed.add_field(name="Direction", value=p.get("direction", "long").upper(), inline=True)
    embed.add_field(name="Signal", value=p.get("reason", "—"), inline=False)
    embed.add_field(
        name=f"Current price",
        value=f"₹{p.get('current_price', 0):,.2f}",
        inline=True,
    )
    embed.add_field(
        name=f"Expected price",
        value=f"₹{p.get('expected_price', 0):,.2f}",
        inline=True,
    )
    embed.add_field(
        name=f"Expected return",
        value=f"{p.get('expected_return_pct', 0):+.2f}%",
        inline=True,
    )
    embed.add_field(name="Stop", value=f"₹{p.get('stop_price', 0):,.2f}", inline=True)
    embed.add_field(name="Risk/Reward", value=str(p.get("risk_reward", "—")), inline=True)
    embed.add_field(name="Confidence", value=f"{p.get('confidence', 0) * 100:.0f}%", inline=True)
    embed.add_field(name="Indicators", value=", ".join(p.get("indicators", [])) or "—", inline=False)
    embed.set_footer(
        text=f"ID {p.get('id')} · auto-skips (NO) if unanswered in 5 min"
    )
    return embed


class ProposalView(ui.View):
    def __init__(self, client: QuantLabAPIClient, proposal_id: str):
        super().__init__(timeout=300)
        self.client = client
        self.proposal_id = proposal_id
        self.accepted = False

    @ui.button(label="✔ Accept", style=ButtonStyle.success)
    async def accept(self, interaction, button: ui.Button):
        try:
            result = self.client.advice_approve(self.proposal_id)
        except Exception as e:  # noqa: BLE001
            await interaction.response.send_message(f"❌ Accept failed: {e}", ephemeral=True)
            return
        execution = result.get("execution", {})
        action = execution.get("action")
        if action == "filled":
            self.accepted = True
            txt = (f"✅ **Trade executed** — {execution.get('side', 'BUY').upper()} "
                   f"@ ₹{execution.get('fill_price', '?')}")
        elif action == "partial":
            self.accepted = True
            txt = (f"🕓 **Partially filled** — {execution.get('side', 'BUY').upper()} "
                   f"@ ₹{execution.get('fill_price', '?')}")
        elif action == "skipped":
            txt = (f"⏹ **Skipped — {execution.get('reason', 'no reason')}**. "
                   f"Order not placed (market closed / no open position).")
        elif action == "rejected":
            txt = f"⛔ **Rejected by risk** — {execution.get('reason', '')}"
        elif action == "failed":
            txt = f"❌ **Execution failed** — {execution.get('error', 'unknown error')}"
        elif action == "none":
            txt = f"⏹ **No trade** — {execution.get('reason', 'neutral signal')}"
        elif result.get("approved"):
            self.accepted = True
            txt = f"✅ **Approved** — execution pending."
        else:
            txt = f"⏹ Not executed: {result.get('reason', result.get('status'))}"
        await interaction.response.edit_message(content=txt, view=None, embed=None)
        self.stop()

    @ui.button(label="✖ Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction, button: ui.Button):
        try:
            result = self.client.advice_cancel(self.proposal_id)
        except Exception as e:  # noqa: BLE001
            await interaction.response.send_message(f"❌ Cancel failed: {e}", ephemeral=True)
            return
        self.accepted = False
        await interaction.response.edit_message(
            content=f"⏹ Trade **cancelled** — no order placed.", view=None, embed=None
        )
        self.stop()

    async def on_timeout(self):
        # Default-NO: if nobody answered, expire on the server side too.
        try:
            self.client.advice_cancel(self.proposal_id)
        except Exception:  # noqa: BLE001
            pass


class AdviceCog(commands.Cog):
    def __init__(self, bot: commands.Bot, client: QuantLabAPIClient, cfg: DiscordBotConfig):
        self.bot = bot
        self.client = client
        self.cfg = cfg
        self._announced: set[str] = set()
        self._started_at = time.time()

    def cog_load(self):
        if self.cfg.advice_auto_start:
            self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    @tasks.loop(seconds=15)
    async def poll_loop(self):
        """Poll new pending proposals and post them as attention embeds."""
        try:
            pending = self.client.advice_proposals("pending")
        except Exception:  # noqa: BLE001 — API may be briefly down
            return
        for p in pending:
            pid = p.get("id")
            if pid in self._announced:
                continue
            self._announced.add(pid)
            chan = await self._target_channel()
            if chan is None:
                continue
            try:
                await chan.send(embed=_proposal_embed(p), view=ProposalView(self.client, pid))
            except Exception:  # noqa: BLE001
                continue

    async def _target_channel(self):
        if self.cfg.advice_channel_id:
            return self.bot.get_channel(self.cfg.advice_channel_id)
        for guild in self.bot.guilds:
            for chan in sorted(guild.text_channels, key=lambda c: c.position):
                return chan
        return None

    @app_commands.command(name="quantlab-advice", description="List pending trade proposals")
    async def cmd_advice(self, interaction):
        await interaction.response.defer()
        try:
            pending = self.client.advice_proposals("pending")
        except Exception as e:  # noqa: BLE001
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
            return
        if not pending:
            await interaction.followup.send("No pending trade proposals.", ephemeral=True)
            return
        for p in pending:
            await interaction.followup.send(embed=_proposal_embed(p), view=ProposalView(self.client, p["id"]))