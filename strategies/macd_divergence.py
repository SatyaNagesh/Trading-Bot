import pandas as pd
import pandas_ta as ta


class MACDStrategy:
    name = 'macd_divergence'
    display = 'MACD Momentum'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 100:
            return []
        df = df.copy()
        mf = params['macd_fast']
        ms = params['macd_slow']
        msig = params['macd_signal']
        adx_p = params['adx_period']

        exp_fast = df['Close'].ewm(span=mf, adjust=False).mean()
        exp_slow = df['Close'].ewm(span=ms, adjust=False).mean()
        df['MACD'] = exp_fast - exp_slow
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=msig, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']
        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        df['EMA_50'] = ta.ema(df['Close'], length=50)

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['MACD']) or pd.isna(last['MACD_SIGNAL']):
            return []

        ema50_slope = (last['EMA_50'] - df['EMA_50'].iloc[-5]) / df['EMA_50'].iloc[-5] if len(df) >= 5 else 0
        hist_rising = last['MACD_HIST'] > prev['MACD_HIST']
        above_trend = pd.isna(last['SMA_200']) or last['Close'] > last['SMA_200']
        below_trend = pd.isna(last['SMA_200']) or last['Close'] < last['SMA_200']

        macd_below_zero_bars = (df['MACD'].iloc[-10:] < 0).sum() if len(df) >= 10 else 0

        if above_trend and prev['MACD'] <= 0 and last['MACD'] > 0:
            if hist_rising and last['RSI'] > 50 and last['RSI'] < 70 and ema50_slope > 0 and macd_below_zero_bars >= 3:
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 1.04, 2),
                    'stop': round(last['Close'] * 0.985, 2),
                    'reason': f"MACD crossed above zero + hist rising, RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': 0,
                    'strategy': self.name,
                })

        macd_above_zero_bars = (df['MACD'].iloc[-10:] > 0).sum() if len(df) >= 10 else 0

        elif below_trend and prev['MACD'] >= 0 and last['MACD'] < 0:
            if last['MACD_HIST'] < prev['MACD_HIST'] and last['RSI'] < 50 and last['RSI'] > 30 and ema50_slope < 0 and macd_above_zero_bars >= 3:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 0.96, 2),
                    'stop': round(last['Close'] * 1.015, 2),
                    'reason': f"MACD crossed below zero + hist falling, RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': 0,
                    'strategy': self.name,
                })

        return signals
