import pandas as pd


class MACDStrategy:
    name = 'macd_divergence'
    display = 'MACD Divergence'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()
        mf = params['macd_fast']
        ms = params['macd_slow']
        msig = params['macd_signal']

        exp_fast = df['Close'].ewm(span=mf, adjust=False).mean()
        exp_slow = df['Close'].ewm(span=ms, adjust=False).mean()
        df['MACD'] = exp_fast - exp_slow
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=msig, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['MACD']) or pd.isna(last['MACD_SIGNAL']):
            return []

        if prev['MACD'] <= prev['MACD_SIGNAL'] and last['MACD'] > last['MACD_SIGNAL']:
            if last['MACD_HIST'] > 0 and last['MACD_HIST'] > prev['MACD_HIST']:
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 1.07, 2),
                    'stop': round(last['Close'] * 0.95, 2),
                    'reason': f"MACD bullish crossover + histogram expanding. RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': 0,
                    'strategy': self.name,
                })

        elif prev['MACD'] >= prev['MACD_SIGNAL'] and last['MACD'] < last['MACD_SIGNAL']:
            if last['MACD_HIST'] < 0 and last['MACD_HIST'] < prev['MACD_HIST']:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 0.93, 2),
                    'stop': round(last['Close'] * 1.07, 2),
                    'reason': f"MACD bearish crossover + histogram declining. RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': 0,
                    'strategy': self.name,
                })

        return signals
