import sys
from datetime import datetime, timezone
from config import WATCHLIST, DISCORD_WEBHOOK_URL
from backtest import BacktestEngine
from notify import send_report


def main():
    tickers = sys.argv[1:] if len(sys.argv) > 1 else WATCHLIST[:3]

    print(f"Running backtest on {', '.join(tickers)}...")
    print(f"Using {BacktestEngine.__init__.__defaults__[0]:,} initial capital")
    print("=" * 70)

    all_results = []
    for ticker in tickers:
        print(f"\n  Fetching {ticker} ({BacktestEngine.__init__.__defaults__[0]} years)...")
        engine = BacktestEngine()
        df = engine.fetch_history(ticker)
        if df.empty:
            print(f"  {ticker}: no data available")
            continue

        print(f"  Data points: {len(df)}")
        result = engine.run(df, ticker)
        all_results.append(result)

        print(f"  Trades: {result['total_trades']}")
        print(f"  Win Rate: {result['win_rate']}%")
        print(f"  Total Return: {result['total_return_pct']:+.2f}%")
        print(f"  Max Drawdown: -{result['max_drawdown_pct']}%")
        print(f"  Sharpe: {result['sharpe_ratio']}")
        print(f"  Profit Factor: {result['profit_factor']}")
        print(f"  Kelly: {result['kelly_pct']}%")

    print("=" * 70)
    print("\nTrade Logs:")
    for r in all_results:
        print(f"\n--- {r['ticker']} ---")
        engine = BacktestEngine()
        df = engine.fetch_history(r['ticker'])
        result = engine.run(df, r['ticker'])
        if engine.trades:
            print(engine.summary())

    avg_return = sum(r['total_return_pct'] for r in all_results) / len(all_results) if all_results else 0
    avg_sharpe = sum(r['sharpe_ratio'] for r in all_results) / len(all_results) if all_results else 0
    avg_win = sum(r['win_rate'] for r in all_results) / len(all_results) if all_results else 0

    summary_lines = [
        f"**Period:** {all_results[0]['start_date']} → {all_results[0]['end_date']} ({all_results[0]['years']} years)" if all_results else "",
        f"**Avg Return:** {avg_return:+.2f}%",
        f"**Avg Sharpe:** {avg_sharpe}",
        f"**Avg Win Rate:** {avg_win}%",
        f"**Stocks Tested:** {len(all_results)}",
    ]

    if all_results and DISCORD_WEBHOOK_URL:
        send_report(DISCORD_WEBHOOK_URL, '📊 Backtest Results', [l for l in summary_lines if l])
        print("\nReport sent to Discord.")

    print(f"\nDone at {datetime.now(timezone.utc).isoformat()}")


if __name__ == '__main__':
    main()
