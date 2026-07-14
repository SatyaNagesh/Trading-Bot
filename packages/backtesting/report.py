"""Report generation for backtest results."""

from packages.domain.models import BacktestResult
from packages.core.logging import get_logger

logger = get_logger("reports")


def generate_summary(result: BacktestResult) -> str:
    lines = [
        "=" * 60,
        "BACKTEST RESULTS",
        "=" * 60,
        f"Total Return:       {result.total_return:.2f}%",
        f"Annualized Return:  {result.annualized_return:.2f}%",
        f"Sharpe Ratio:       {result.sharpe_ratio:.2f}",
        f"Sortino Ratio:      {result.sortino_ratio:.2f}",
        f"Max Drawdown:       {result.max_drawdown:.2f}%",
        f"Win Rate:           {result.win_rate:.2f}%",
        f"Profit Factor:      {result.profit_factor:.2f}",
        f"Total Trades:       {result.total_trades}",
        "-" * 60,
    ]
    if result.equity_curve:
        start = result.equity_curve[0]["equity"]
        end = result.equity_curve[-1]["equity"]
        lines.append(f"Start Equity:       ${start:,.2f}")
        lines.append(f"End Equity:         ${end:,.2f}")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_csv(result: BacktestResult) -> str:
    if not result.equity_curve:
        return "bar,equity,cash,drawdown"
    lines = ["bar,equity,cash,drawdown"]
    for point in result.equity_curve:
        lines.append(
            f"{point['bar']},{point['equity']:.2f},{point['cash']:.2f},{point['drawdown']:.6f}"
        )
    return "\n".join(lines)
