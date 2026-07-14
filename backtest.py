import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone

from config import BACKTEST_YEARS, BACKTEST_INTERVAL, INDICATOR_PARAMS
from risk import (calculate_sharpe, calculate_sortino, calculate_calmar,
                  max_drawdown, kelly_criterion)
from ensemble import run_all_strategies


class BacktestEngine:
    def __init__(self, initial_capital: float = 100000):
        self.capital = initial_capital
        self.trades = []
        self.equity_curve = []
        self.returns = []

    def fetch_history(self, ticker: str) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=BACKTEST_YEARS * 365)
        stock = yf.Ticker(ticker)
        df = stock.history(start=start, end=end, interval=BACKTEST_INTERVAL)
        return df

    def run(self, df: pd.DataFrame, ticker: str) -> dict:
        df = df.copy()
        position = 0
        cash = self.capital
        shares = 0
        equity = self.capital
        peak = self.capital
        max_dd = 0
        trade_count = 0
        wins = 0
        losses = 0
        total_win_pct = 0
        total_loss_pct = 0

        for i in range(100, len(df)):
            window = df.iloc[:i + 1]
            signals = run_all_strategies(window, INDICATOR_PARAMS)

            buy = [s for s in signals if s['type'] == 'BUY']
            sell = [s for s in signals if s['type'] == 'SELL']

            price = df.iloc[i]['Close']

            if buy and position == 0:
                shares = cash * 0.95 / price
                cash -= shares * price
                position = 1
                self.trades.append({
                    'entry_date': df.iloc[i].name,
                    'entry_price': price,
                    'type': 'BUY',
                    'strategies': buy[0]['strategy'],
                })

            elif sell and position > 0:
                entry = self.trades[-1]['entry_price']
                pnl_pct = (price - entry) / entry * 100
                cash += shares * price
                position = 0
                trade_count += 1
                self.trades[-1]['exit_date'] = df.iloc[i].name
                self.trades[-1]['exit_price'] = price
                self.trades[-1]['pnl_pct'] = round(pnl_pct, 2)

                if pnl_pct > 0:
                    wins += 1
                    total_win_pct += pnl_pct
                else:
                    losses += 1
                    total_loss_pct += abs(pnl_pct)

            equity_val = cash + (shares * price if position else 0)
            self.equity_curve.append(equity_val)
            peak = max(peak, equity_val)
            dd = (equity_val - peak) / peak * 100
            max_dd = min(max_dd, dd)

        if position > 0:
            cash += shares * df.iloc[-1]['Close']
            position = 0

        final_equity = cash
        total_return = (final_equity - self.capital) / self.capital * 100
        eq_series = pd.Series(self.equity_curve)
        ret_series = eq_series.pct_change().dropna()

        win_rate = wins / trade_count * 100 if trade_count > 0 else 0
        avg_win = total_win_pct / wins if wins > 0 else 0
        avg_loss = total_loss_pct / losses if losses > 0 else 0
        kelly = kelly_criterion(win_rate / 100, avg_win, avg_loss) if wins > 0 and losses > 0 else 0
        profit_factor = total_win_pct / total_loss_pct if total_loss_pct > 0 else float('inf')

        return {
            'ticker': ticker,
            'total_return_pct': round(total_return, 2),
            'final_equity': round(final_equity, 2),
            'total_trades': trade_count,
            'win_rate': round(win_rate, 1),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'kelly_pct': round(kelly * 100, 1),
            'max_drawdown_pct': round(abs(max_dd), 2),
            'sharpe_ratio': calculate_sharpe(ret_series) if len(ret_series) > 0 else 0,
            'sortino_ratio': calculate_sortino(ret_series) if len(ret_series) > 0 else 0,
            'calmar_ratio': calculate_calmar(ret_series, eq_series) if len(ret_series) > 0 else 0,
            'start_date': str(df.index[0].date()) if not df.empty else '',
            'end_date': str(df.index[-1].date()) if not df.empty else '',
            'years': round((df.index[-1] - df.index[0]).days / 365, 1) if not df.empty else 0,
        }

    def summary(self) -> str:
        if not self.trades:
            return "No trades executed."
        lines = []
        for t in self.trades:
            if 'pnl_pct' in t:
                lines.append(
                    f"{t['entry_date'].date()} {t['type']} @ ₹{t['entry_price']:.2f} "
                    f"→ {t['exit_date'].date()} @ ₹{t['exit_price']:.2f} "
                    f"P&L: {t['pnl_pct']:+.2f}%"
                )
        return '\n'.join(lines)
