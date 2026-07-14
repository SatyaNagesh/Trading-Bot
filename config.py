import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://dnstcdkjgcmrhcukrjgw.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRuc3RjZGtqZ2NtcmhjdWtyamd3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI2MzA1NzksImV4cCI6MjA5ODIwNjU3OX0.FZ5Y5bGw24w0wIEG9VuhhVPJWXXviOOmvLheLuCiTgw')

WATCHLIST = [
    'INFY.NS',
    'RELIANCE.NS',
    'TCS.NS',
    'HDFCBANK.NS',
    'ICICIBANK.NS',
    'SBIN.NS',
    'BHARTIARTL.NS',
    'ITC.NS',
    'WIPRO.NS',
    'HINDUNILVR.NS',
]

BACKTEST_YEARS = 5
BACKTEST_INTERVAL = '1d'

LIVE_INTERVAL = '1h'
LIVE_PERIOD = '1mo'

INDICATOR_PARAMS = {
    'ema_fast': 20,
    'ema_slow': 50,
    'ema_trend': 200,
    'rsi_period': 14,
    'rsi_overbought': 75,
    'rsi_oversold': 25,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2.0,
    'volume_sma_period': 20,
    'volume_threshold': 1.3,
    'adx_period': 14,
    'adx_threshold': 25,
}

RISK_PARAMS = {
    'max_portfolio_risk_pct': 0.02,
    'kelly_fraction': 0.25,
    'max_drawdown_pct': 15,
    'volatility_lookback': 20,
    'position_size_pct': 0.05,
}

REGIME_PARAMS = {
    'trend_lookback': 50,
    'volatility_lookback': 20,
    'sideways_threshold': 0.03,
}

ENSEMBLE_PARAMS = {
    'min_votes': 1,
    'require_regime_match': True,
}
