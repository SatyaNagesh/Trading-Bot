"""Operational Dashboard — lightweight CLI dashboard for paper trading visibility."""

from datetime import datetime, timezone

from packages.core.logging import get_logger
from packages.portfolio.engine import PortfolioEngine
from packages.risk.engine import RiskEngine
from packages.health.monitor import HealthMonitor
from packages.journal.entry import TradeJournal
from packages.session.manager import SessionManager
from packages.oms.manager import OrderManager

logger = get_logger("dashboard")

SEPARATOR = "═" * 60


class Dashboard:
    def __init__(
        self,
        portfolio_engine: PortfolioEngine | None = None,
        risk_engine: RiskEngine | None = None,
        health_monitor: HealthMonitor | None = None,
        trade_journal: TradeJournal | None = None,
        session_manager: SessionManager | None = None,
        order_manager: OrderManager | None = None,
    ):
        self.portfolio = portfolio_engine
        self.risk = risk_engine
        self.health = health_monitor
        self.journal = trade_journal
        self.session = session_manager
        self.oms = order_manager

    def render(self) -> str:
        lines = [
            SEPARATOR,
            "  QUANTLAB AI — PAPER TRADING DASHBOARD",
            f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            SEPARATOR,
            "",
        ]

        lines.extend(self._render_session())
        lines.extend(self._render_portfolio())
        lines.extend(self._render_positions())
        lines.extend(self._render_risk())
        lines.extend(self._render_orders())
        lines.extend(self._render_journal())
        lines.extend(self._render_health())

        lines.append(SEPARATOR)
        return "\n".join(lines)

    def _render_session(self) -> list[str]:
        if not self.session:
            return []
        s = self.session.status()
        return [
            "  📅 SESSION",
            f"     Status:     {s['session']}",
            f"     Calendar:   {s['calendar']}",
            f"     Next Open:  {s.get('next_open', 'N/A')}",
            "",
        ]

    def _render_portfolio(self) -> list[str]:
        if not self.portfolio:
            return []
        p = self.portfolio.to_dict()
        return [
            "  💰 PORTFOLIO",
            f"     Initial Capital:  ${p['initial_capital']:,.2f}",
            f"     Cash:             ${p['cash']:,.2f}",
            f"     Equity:           ${p['equity']:,.2f}",
            f"     Buying Power:     ${p['buying_power']:,.2f}",
            f"     NAV:              ${p['nav']:,.2f}",
            f"     Unrealized PnL:   ${p['unrealized_pnl']:+,.2f}",
            f"     Realized PnL:     ${p['realized_pnl']:+,.2f}",
            f"     Total Return:     {p['total_return_pct']:+.2f}%",
            f"     Daily Return:     {p['daily_return_pct']:+.2f}%",
            f"     Drawdown:         {p['drawdown_pct']:.2f}%",
            f"     Exposure:         {p['exposure_pct']:.1f}%",
            f"     Open Positions:   {p['open_positions']}",
            f"     Closed Trades:    {p['closed_trades']}",
            "",
        ]

    def _render_positions(self) -> list[str]:
        if not self.portfolio:
            return []
        positions = self.portfolio.get_all_positions()
        if not positions:
            return ["  📊 POSITIONS", "     (none)", ""]
        lines = ["  📊 POSITIONS"]
        for p in positions:
            lines.append(
                f"     {p.symbol:8s} {p.side.value:5s}  "
                f"Qty:{p.quantity:5d}  "
                f"Avg:${float(p.average_price):8.2f}  "
                f"Cur:${float(p.current_price):8.2f}  "
                f"PnL:${float(p.pnl):+8.2f}  ({p.pnl_pct:+.2f}%)"
            )
        lines.append("")
        return lines

    def _render_risk(self) -> list[str]:
        if not self.risk:
            return []
        r = self.risk.summary()
        return [
            "  🛡️ RISK ENGINE",
            f"     Kill Switch:     {'ACTIVE ⛔' if r['kill_switch_active'] else 'Inactive ✅'}",
            f"     Daily Loss:      {r['daily_loss']:.2f}",
            f"     Daily Trades:    {r['daily_trades']}",
            f"     Rejected Orders: {r['total_rejected']}",
            f"     Max Drawdown:    {r['max_drawdown']:.1f}%",
            f"     Max Daily Loss:  {r['max_daily_loss']:.1f}%",
            f"     Max Positions:   {r['max_positions']}",
            f"     Max Exposure:    {r['max_exposure_pct']:.1f}%",
            f"     Max Leverage:    {r['max_leverage']}x",
            "",
        ]

    def _render_orders(self) -> list[str]:
        if not self.oms:
            return []
        orders = self.oms.get_open_orders()
        if not orders:
            return ["  📋 PENDING ORDERS", "     (none)", ""]
        lines = ["  📋 PENDING ORDERS"]
        for o in orders[:10]:
            lines.append(
                f"     {o.id[:8]:8s} {o.symbol:8s} {o.side.value:4s} "
                f"Qty:{o.quantity:5d} Filled:{o.filled_quantity:5d} "
                f"Status:{o.status.value:10s}"
            )
        lines.append("")
        return lines

    def _render_journal(self) -> list[str]:
        if not self.journal:
            return []
        s = self.journal.summary()
        return [
            "  📓 TRADE JOURNAL",
            f"     Total Trades:  {s['total_trades']}",
            f"     Total PnL:     ${s['total_pnl']:+,.2f}",
            f"     Win Rate:      {s['win_rate']:.1f}%",
            f"     Avg PnL:       ${s['avg_pnl']:+,.2f}",
            f"     Strategies:    {s['strategies']}",
            f"     Symbols:       {s['symbols']}",
            "",
        ]

    def _render_health(self) -> list[str]:
        if not self.health:
            return []
        h = self.health.report()
        status_icon = "✅" if h["healthy"] else "⛔"
        return [
            "  ❤️ HEALTH MONITOR",
            f"     Overall:          {status_icon} {'Healthy' if h['healthy'] else 'Degraded'}",
            f"     Broker:           {'✅' if h['broker_connected'] else '❌'}",
            f"     Market Data:      {'✅' if h['market_data_available'] else '❌'}",
            f"     Risk Engine:      {'✅' if h['risk_engine_healthy'] else '❌'}",
            f"     Portfolio:        {'✅' if h['portfolio_integrity'] else '❌'}",
            f"     Trading Paused:   {'⚠️  PAUSED' if h['trading_paused'] else 'Normal'}",
            f"     API Failures:     {h['api_failures']}",
            f"     System Exceptions:{h['system_exceptions']}",
            f"     Alerts:           {h['recent_alerts']}",
            "",
        ]
