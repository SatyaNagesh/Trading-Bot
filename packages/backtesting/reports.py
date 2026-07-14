"""Report generation — weekly/monthly strategy performance reports."""

from datetime import datetime, timedelta, timezone
from typing import Any

from packages.core.logging import get_logger

logger = get_logger("report_generation")


def generate_weekly_report(strategies: list[dict]) -> str:
    lines = ["# QuantLab AI — Weekly Strategy Report", f"**Week of {datetime.now(timezone.utc).strftime('%B %d, %Y')}**\n"]
    lines.append("| Strategy | Sharpe | Return% | Drawdown% | Status |")
    lines.append("|----------|--------|---------|-----------|--------|")
    for s in strategies:
        lines.append(
            f"| {s.get('name', '?')} | {s.get('sharpe', 0):.2f} | "
            f"{s.get('total_return', 0):.1f}% | {s.get('max_drawdown', 0):.1f}% | "
            f"{s.get('status', 'unknown')} |"
        )
    return "\n".join(lines)


def generate_monthly_report(strategies: list[dict], trades: list[dict]) -> str:
    lines = [
        "# QuantLab AI — Monthly Strategy Report",
        f"**{datetime.now(timezone.utc).strftime('%B %Y')}**\n",
        "## Executive Summary\n",
        f"- Active Strategies: {len(strategies)}",
        f"- Total Trades: {len(trades)}",
    ]
    if trades:
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        win_trades = [t for t in trades if t.get("pnl", 0) > 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        lines.extend([
            f"- Total P&L: {total_pnl:.2f}",
            f"- Win Rate: {win_rate:.1f}%",
        ])
    lines.extend(["\n## Strategy Details\n"])
    for s in strategies:
        lines.append(f"### {s.get('name', '?')}")
        lines.append(f"- Sharpe: {s.get('sharpe', 0):.2f}")
        lines.append(f"- Return: {s.get('total_return', 0):.1f}%")
        lines.append(f"- Max DD: {s.get('max_drawdown', 0):.1f}%")
        lines.append("")
    return "\n".join(lines)
