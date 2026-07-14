import pandas as pd
import pandas_ta as ta


class AlphaTrendStrategy:
    name = 'alphatrend'
    display = 'AlphaTrend'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()

        AP = params.get('alphatrend_period', 14)
        coeff = params.get('alphatrend_multiplier', 1.0)
        high = df['High']
        low = df['Low']

        df['TR'] = ta.true_range(high, low, df['Close'])
        df['ATR'] = df['TR'].rolling(window=AP).mean()
        df['MFI'] = ta.mfi(high, low, df['Close'], df['Volume'], length=AP)
        df['RSI'] = ta.rsi(df['Close'], length=14)

        upT = low - df['ATR'] * coeff
        downT = high + df['ATR'] * coeff

        alpha = [0.0] * len(df)
        for i in range(1, len(df)):
            mfi_val = df['MFI'].iloc[i]
            if pd.isna(mfi_val):
                alpha[i] = alpha[i-1]
                continue
            if mfi_val >= 50:
                alpha[i] = upT.iloc[i] if upT.iloc[i] > alpha[i-1] else alpha[i-1]
            else:
                alpha[i] = downT.iloc[i] if downT.iloc[i] < alpha[i-1] else alpha[i-1]
        df['ALPHA'] = alpha

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        p2 = df.iloc[-3] if len(df) >= 3 else prev

        if pd.isna(last['ALPHA']) or pd.isna(prev['ALPHA']) or pd.isna(p2['ALPHA']):
            return []

        alpha_buy = last['ALPHA'] > p2['ALPHA'] and prev['ALPHA'] <= p2['ALPHA']
        alpha_sell = last['ALPHA'] < p2['ALPHA'] and prev['ALPHA'] >= p2['ALPHA']

        if alpha_buy:
            atr_stop = last['ATR'] * 1.5
            stop_pct = min(atr_stop / last['Close'], 0.02)
            signals.append({
                'type': 'BUY',
                'price': round(last['Close'], 2),
                'target': round(last['Close'] * 1.04, 2),
                'stop': round(last['Close'] * (1 - stop_pct), 2),
                'reason': f"AlphaTrend crossover BUY, MFI {df['MFI'].iloc[-1]:.0f}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': 0,
                'strategy': self.name,
            })

        elif alpha_sell:
            atr_stop = last['ATR'] * 1.5
            stop_pct = min(atr_stop / last['Close'], 0.02)
            signals.append({
                'type': 'SELL',
                'price': round(last['Close'], 2),
                'target': round(last['Close'] * 0.96, 2),
                'stop': round(last['Close'] * (1 + stop_pct), 2),
                'reason': f"AlphaTrend crossunder SELL, MFI {df['MFI'].iloc[-1]:.0f}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': 0,
                'strategy': self.name,
            })

        return signals
