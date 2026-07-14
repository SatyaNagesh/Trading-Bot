"""QuantLab AI CLI — command-line interface for research and backtesting."""

import asyncio
from datetime import date, timedelta
from decimal import Decimal

import click
import pandas as pd
from tabulate import tabulate

from packages.core.logging import setup_logging, get_logger
from packages.market.data_pipeline import fetch_bars, get_available_symbols
from packages.market.data_quality import validate_bars
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.report import generate_summary, generate_csv
from packages.domain.models import BacktestConfig, BacktestResult, Bar, Signal, SignalDirection
from packages.indicators.api import sma as sma_func, compute_all

setup_logging()
logger = get_logger("cli")


@click.group()
def cli():
    """QuantLab AI — quantitative research operating system."""
    pass


@cli.group()
def data():
    """Market data commands."""
    pass


@data.command()
@click.argument("symbol")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option("--no-cache", is_flag=True, help="Skip cache")
def fetch(symbol: str, start: str | None, end: str | None, no_cache: bool):
    """Fetch market data for a symbol."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    click.echo(f"Fetching {symbol} from {start_date} to {end_date}...")
    bars = _run_async(fetch_bars(symbol, start_date, end_date, use_cache=not no_cache))
    click.echo(f"Fetched {len(bars)} bars")

    warnings = validate_bars(bars, symbol)
    for w in warnings:
        click.echo(f"  ⚠ {w}")


@data.command()
def list_symbols():
    """List available NSE symbols."""
    symbols = get_available_symbols()
    click.echo(tabulate(
        [(i + 1, s) for i, s in enumerate(symbols)],
        headers=["#", "Symbol"],
        tablefmt="simple",
    ))
    click.echo(f"\nTotal: {len(symbols)} symbols")


@cli.group()
def backtest():
    """Backtesting commands."""
    pass


@backtest.command()
@click.argument("symbol")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option("--capital", default=1000000, type=float, help="Initial capital")
@click.option("--output", default=None, help="Output CSV file")
def run(symbol: str, start: str | None, end: str | None, capital: float, output: str | None):
    """Run backtest for a symbol."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    click.echo(f"Running backtest for {symbol}...")
    click.echo(f"  Period: {start_date} to {end_date}")
    click.echo(f"  Capital: ₹{capital:,.0f}")

    result = _run_async(_run_backtest(symbol, start_date, end_date, capital))

    click.echo("")
    click.echo(generate_summary(result))

    if output:
        csv_data = generate_csv(result)
        with open(output, "w") as f:
            f.write(csv_data)
        click.echo(f"Equity curve saved to {output}")


@backtest.command()
@click.argument("symbol")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
def csv(symbol: str, start: str | None, end: str | None):
    """Output backtest equity curve as CSV to stdout."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)
    result = _run_async(_run_backtest(symbol, start_date, end_date, capital=1_000_000))
    click.echo(generate_csv(result))


@cli.command()
@click.argument("symbol")
@click.option("--start", default=None)
@click.option("--end", default=None)
def validate(symbol: str, start: str | None, end: str | None):
    """Validate data quality for a symbol."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    bars = _run_async(fetch_bars(symbol, start_date, end_date))
    click.echo(f"Checking {len(bars)} bars for {symbol}...")

    warnings = validate_bars(bars, symbol)
    if warnings:
        click.echo(f"\nFound {len(warnings)} warnings:")
        for w in warnings:
            click.echo(f"  ⚠ {w}")
    else:
        click.echo("  ✓ No issues found")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _run_async(coro) -> any:
    return asyncio.run(coro)


async def _run_backtest(
    symbol: str,
    start_date: date,
    end_date: date,
    capital: float,
) -> "BacktestResult":
    bars = await fetch_bars(symbol, start_date, end_date)
    if not bars:
        raise click.ClickException("No data available")

    config = BacktestConfig(
        initial_capital=Decimal(str(capital)),
        start_date=start_date,
        end_date=end_date,
    )

    closes = [float(b.close) for b in bars]
    series = pd.Series(closes)
    indicators = compute_all(series)
    sma_20_col = indicators["sma_20"].values
    sma_50_col = indicators["sma_50"].values

    def sma_crossover_strategy(bar: Bar, ctx) -> list[Signal]:
        idx = len(closes) - (len(bars) - bars.index(bar)) + 1
        idx = min(idx - 1, len(sma_20_col) - 1)
        if idx < 0:
            return []

        s20 = sma_20_col[idx]
        s50 = sma_50_col[idx]

        if pd.isna(s20) or pd.isna(s50) or idx < 1:
            return []

        prev_s20 = sma_20_col[idx - 1]
        signals = []

        if not pd.isna(prev_s20):
            if s20 > s50 and prev_s20 <= s50:
                signals.append(Signal(
                    strategy_id="sma_crossover",
                    direction=SignalDirection.LONG,
                    confidence=0.7,
                    reason=["20 SMA crossed above 50 SMA"],
                ))
            elif s20 < s50 and prev_s20 >= s50:
                signals.append(Signal(
                    strategy_id="sma_crossover",
                    direction=SignalDirection.SHORT,
                    confidence=0.7,
                    reason=["20 SMA crossed below 50 SMA"],
                ))

        return signals

    engine = BacktestEngine(config=config, strategy=sma_crossover_strategy)
    return await engine.run({symbol: bars})


if __name__ == "__main__":
    cli()
