import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

from config import SUPABASE_URL, SUPABASE_KEY


class PaperTrade:
    def __init__(self):
        self.positions = {}  # ticker -> {'shares': N, 'entry_price': X, 'entry_date': ...}
        self.cash = 100000
        self.initial_capital = 100000
        self.trades = []

    def buy(self, ticker: str, price: float, reason: str, shares: int = None):
        if shares is None:
            shares = int(self.cash * 0.95 / price)
        cost = shares * price
        if cost > self.cash:
            shares = int(self.cash * 0.95 / price)
            cost = shares * price
        self.cash -= cost
        self.positions[ticker] = {
            'shares': shares,
            'entry_price': price,
            'entry_date': datetime.now(timezone.utc),
        }
        self.trades.append({
            'date': datetime.now(timezone.utc).isoformat(),
            'ticker': ticker,
            'type': 'BUY',
            'price': price,
            'shares': shares,
            'value': cost,
            'reason': reason,
        })

    def sell(self, ticker: str, price: float, reason: str):
        if ticker not in self.positions:
            return None
        pos = self.positions[ticker]
        value = pos['shares'] * price
        pnl = value - (pos['shares'] * pos['entry_price'])
        pnl_pct = (price - pos['entry_price']) / pos['entry_price'] * 100
        self.cash += value
        self.trades.append({
            'date': datetime.now(timezone.utc).isoformat(),
            'ticker': ticker,
            'type': 'SELL',
            'price': price,
            'shares': pos['shares'],
            'value': value,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'reason': reason,
        })
        del self.positions[ticker]
        return {'pnl': round(pnl, 2), 'pnl_pct': round(pnl_pct, 2)}

    def portfolio_value(self, current_prices: dict) -> float:
        total = self.cash
        for ticker, pos in self.positions.items():
            price = current_prices.get(ticker, pos['entry_price'])
            total += pos['shares'] * price
        return total

    def status(self) -> dict:
        return {
            'cash': round(self.cash, 2),
            'positions': len(self.positions),
            'total_trades': len(self.trades),
            'total_pnl': round(sum(t.get('pnl', 0) for t in self.trades if 'pnl' in t), 2),
            'portfolio_value': round(self.cash + sum(
                pos['shares'] * pos['entry_price'] for pos in self.positions.values()
            ), 2),
        }
