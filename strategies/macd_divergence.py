import pandas as pd
import pandas_ta as ta


class MACDStrategy:
    name = 'macd_divergence'
    display = 'MACD Divergence'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 100:
            return []
        df = df.copy()
        mf = params['macd_fast']
        ms = params['macd_slow']
        msig = params['macd_signal']
        adx_p = params['adx_period']
        adx_t = params['adx_threshold']

        exp_fast = df['Close'].ewm(span=mf, adjust=False).mean()
        exp_slow = df['Close'].ewm(span=ms, adjust=False).mean()
        df['MACD'] = exp_fast - exp_slow
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=msig, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])

        adx = ta.adx(df['High'], df['Low'], df['Close'], length=adx_p)
        if adx is not None:
            df['ADX'] = adx[f'ADX_{adx_p}']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        p3 = df.iloc[-3]

        if pd.isna(last['MACD']) or pd.isna(last['MACD_SIGNAL']):
            return []

        if 'ADX' in df.columns and (pd.isna(last['ADX']) or last['ADX'] < adx_t):
            return []

        hist_expanding = (last['MACD_HIST'] > prev['MACD_HIST'] > p3['MACD_HIST'])

        if prev['MACD'] <= prev['MACD_SIGNAL'] and last['MACD'] > last['MACD_SIGNAL']:
            if last['MACD'] > 0 and last['MACD_HIST'] > 0 and hist_expanding:
                if last['RSI'] < 65:
                    signals.append({
                        'type': 'BUY',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 1.05, 2),
                        'stop': round(last['Close'] * 0.975, 2),
                        'reason': f"MACD bullish cross above zero + hist rising, ADX {last.get('ADX', 0):.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': 0,
                        'strategy': self.name,
                    })

        elif prev['MACD'] >= prev['MACD_SIGNAL'] and last['MACD'] < last['MACD_SIGNAL']:
            if last['MACD'] < 0 and last['MACD_HIST'] < 0 and hist_expanding:
                if last['RSI'] > 35:
                    signals.append({
                        'type': 'SELL',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 0.95, 2),
                        'stop': round(last['Close'] * 1.025, 2),
                        'reason': f"MACD bearish cross below zero + hist declining, ADX {last.get('ADX', 0):.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': 0,
                        'strategy': self.name,
                    })

        return signals
