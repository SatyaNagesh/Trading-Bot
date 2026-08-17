"""Discord slash commands — all delegate to the API client."""

from discord import Embed, Color, app_commands
from discord.ext import commands

from services.discord_bot.api_client import QuantLabAPIClient


def _trade_callout_summary(client: QuantLabAPIClient, symbol: str, side: str, price: float | None) -> str:
    req = {"symbol": symbol, "side": side, "price": price}
    result = client.manual_trade(**{k: v for k, v in req.items() if v is not None})
    execu = result.get("execution", {})
    action = execu.get("action")
    pre = f"{req['symbol']} {side.upper()}"
    if action == "filled":
        return (f"✅ **{pre} filled** — {execu.get('side', side).upper()} "
                f"@ ₹{execu.get('fill_price', '?')} · qty {execu.get('quantity', '?')}")
    if action == "partial":
        return f"🕓 **{pre} partially filled** @ ₹{execu.get('fill_price', '?')}"
    if action == "skipped":
        return f"⏹ **{pre} skipped — {execu.get('reason', 'no reason')}** (market closed / no open position)"
    if action == "rejected":
        return f"⛔ **{pre} rejected by risk** — {execu.get('reason', '')}"
    if action == "failed":
        return f"❌ **{pre} failed** — {execu.get('error', 'unknown error')}"
    if action == "none":
        return f"⏹ **{pre} no trade** — {execu.get('reason', 'neutral signal')}"
    return f"ℹ️ **{pre}** — {result.get('execution')}"


def _status_embed(client: QuantLabAPIClient) -> Embed:
    try:
        ts = client.trading_status()
        ps = client.portfolio_summary()
        rs = client.risk_summary()
        ac = client.alert_counts()
        sc = client.order_counts()
        embed = Embed(title="QuantLab AI — Status", color=Color.blue())
        embed.add_field(name="Running", value="✅ Yes" if ts.get("running") else "❌ No", inline=True)
        embed.add_field(name="Cycle Count", value=str(ts.get("cycle_count", 0)), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="NAV", value=f"₹{ps.get('net_asset_value', 0):,.2f}", inline=True)
        embed.add_field(name="Open Positions", value=str(ps.get("open_positions", 0)), inline=True)
        embed.add_field(name="Total PnL", value=f"₹{ps.get('total_pnl', 0):,.2f}", inline=True)
        embed.add_field(name="Daily Loss", value=f"₹{rs.get('daily_loss', 0):,.2f}", inline=True)
        embed.add_field(name="Kill Switch", value="🔴 Active" if rs.get("kill_switch_active") else "🟢 Inactive", inline=True)
        embed.add_field(name="Rejected Orders", value=str(rs.get("total_rejected", 0)), inline=True)
        embed.add_field(name="Orders Pending", value=str(sc.get("pending", 0)), inline=True)
        embed.add_field(name="Alerts", value=f"{ac.get('total', 0)} ({ac.get('critical', 0)} critical)", inline=True)
        embed.add_field(name="Trades Executed", value=str(ps.get("total_trades", 0)), inline=True)
        embed.set_footer(text="QuantLab AI v0.1.0-rc1")
        return embed
    except Exception as e:
        return Embed(title="Error", description=str(e), color=Color.red())


def _positions_embed(client: QuantLabAPIClient) -> Embed:
    try:
        positions = client.portfolio_positions()
        embed = Embed(title="QuantLab AI — Open Positions", color=Color.green())
        if not positions:
            embed.description = "No open positions"
        for p in positions:
            pnl_str = f"₹{p['pnl']:+,.2f}" if p.get("pnl") is not None else "N/A"
            embed.add_field(
                name=f"{p['symbol']} ({p['strategy_id']})",
                value=f"Qty: {p['quantity']} | PnL: {pnl_str} | Entry: ₹{p['entry_price']:,.2f}",
                inline=False,
            )
        return embed
    except Exception as e:
        return Embed(title="Error", description=str(e), color=Color.red())


def _rankings_embed(client: QuantLabAPIClient) -> Embed:
    try:
        rankings = client.strategy_rankings(top_n=5)
        embed = Embed(title="QuantLab AI — Top Strategies", color=Color.gold())
        if not rankings:
            embed.description = "No strategies ranked yet"
        for r in rankings:
            embed.add_field(
                name=f"{r['name']} ({r['strategy_id'][:8]}...)",
                value=f"Score: {r['score']:.4f} | Sharpe: {r['sharpe']:.2f}",
                inline=False,
            )
        return embed
    except Exception as e:
        return Embed(title="Error", description=str(e), color=Color.red())


class QuantLabCog(commands.Cog):
    def __init__(self, bot: commands.Bot, client: QuantLabAPIClient):
        self.bot = bot
        self.client = client

    @app_commands.command(name="quantlab-status", description="Show QuantLab trading status")
    async def cmd_status(self, interaction):
        await interaction.response.defer()
        embed = _status_embed(self.client)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quantlab-positions", description="Show open positions")
    async def cmd_positions(self, interaction):
        await interaction.response.defer()
        embed = _positions_embed(self.client)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quantlab-rankings", description="Show top ranked strategies")
    async def cmd_rankings(self, interaction):
        await interaction.response.defer()
        embed = _rankings_embed(self.client)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quantlab-start", description="Start the trading engine")
    async def cmd_start(self, interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = self.client.trading_start()
            await interaction.followup.send(f"✅ Trading started: {result}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="quantlab-stop", description="Stop the trading engine")
    async def cmd_stop(self, interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            result = self.client.trading_stop(reason=f"Discord command by {interaction.user}")
            await interaction.followup.send(f"⏹ Trading stopped: {result}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="quantlab-health", description="Show QuantLab health status")
    async def cmd_health(self, interaction):
        await interaction.response.defer()
        try:
            h = self.client.health()
            r = self.client.ready()
            embed = Embed(title="QuantLab AI — Health", color=Color.green() if r.get("ready") else Color.orange())
            embed.add_field(name="API Status", value=h.get("status", "unknown"), inline=True)
            embed.add_field(name="Ready", value="✅ Yes" if r.get("ready") else "❌ No", inline=True)
            embed.add_field(name="Database", value="✅ OK" if r.get("database_accessible") else "❌ Down", inline=True)
            embed.add_field(name="Bot Running", value="✅ Yes" if r.get("bot_running") else "❌ No", inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(embed=Embed(title="Error", description=str(e), color=Color.red()))

    @app_commands.command(name="quantlab-trade", description="Manually call out a long/short trade (auto-sized, respects market hours)")
    @app_commands.describe(symbol="Ticker symbol, e.g. RELIANCE.NS", side="Direction: long or short", price="Optional override price (defaults to last cached close)")
    async def cmd_trade(self, interaction, symbol: str, side: str = "long", price: float | None = None):
        await interaction.response.defer()
        try:
            msg = _trade_callout_summary(self.client, symbol.strip().upper(), side, price)
        except Exception as e:
            msg = f"❌ **Trade call-out failed** — {e}"
        await interaction.followup.send(msg)

    @app_commands.command(name="quantlab-help", description="Show available QuantLab commands")
    async def cmd_help(self, interaction):
        embed = Embed(title="QuantLab AI — Commands", color=Color.blue())
        embed.add_field(name="/quantlab-status", value="Trading engine status", inline=False)
        embed.add_field(name="/quantlab-positions", value="Open positions", inline=False)
        embed.add_field(name="/quantlab-rankings", value="Top ranked strategies", inline=False)
        embed.add_field(name="/quantlab-trade <symbol> <long|short> [price]", value="Manually call out a trade", inline=False)
        embed.add_field(name="/quantlab-advice", value="List pending trade proposals", inline=False)
        embed.add_field(name="/quantlab-start", value="Start the engine", inline=False)
        embed.add_field(name="/quantlab-stop", value="Stop the engine", inline=False)
        embed.add_field(name="/quantlab-health", value="API health check", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
