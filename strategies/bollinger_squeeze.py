import pandas as pd
import pandas_ta as ta


class BollingerStrategy:
    name = 'bollinger_squeeze'
    display = 'Bollinger Squeeze'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 30:
            return []
        df = df.copy()
        bb_p = params['bb_period']
        bb_s = params['bb_std']

        bb = ta.bbands(df['Close'], length=bb_p, std=bb_s)
        if bb is None:
            return []

        df['BB_UPPER'] = bb[f'BBU_{bb_p}_{bb_s}']
        df['BB_MID'] = bb[f'BBM_{bb_p}_{bb_s}']
        df['BB_LOWER'] = bb[f'BBL_{bb_p}_{bb_s}']
        df['BB_WIDTH'] = (df['BB_UPPER'] - df['BB_LOWER']) / df['BB_MID']
        df['BB_PCT'] = (df['Close'] - df['BB_LOWER']) / (df['BB_UPPER'] - df['BB_LOWER'])

        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])
        df['VOL_SMA'] = df['Volume'].rolling(window=20).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['BB_WIDTH']):
            return []

        width_avg = df['BB_WIDTH'].rolling(window=20).mean().iloc[-1]
        is_squeeze = last['BB_WIDTH'] < width_avg * 0.8

        if is_squeeze and last['BB_PCT'] > 0.95 and prev['BB_PCT'] <= 0.95:
            vol_note = f" + Volume {last['VOL_RATIO']:.1f}x" if last['VOL_RATIO'] > 1.5 else ""
            signals.append({
                'type': 'BUY',
                'price': round(last['Close'], 2),
                'target': round(last['BB_UPPER'] * 1.03, 2),
                'stop': round(last['BB_LOWER'] * 0.97, 2),
                'reason': f"Bollinger squeeze breakout upward{vol_note}. RSI {last['RSI']:.0f}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': round(last['VOL_RATIO'], 1),
                'strategy': self.name,
            })

        elif is_squeeze and last['BB_PCT'] < 0.05 and prev['BB_PCT'] >= 0.05:
            signals.append({
                'type': 'SELL',
                'price': round(last['Close'], 2),
                'target': round(last['BB_LOWER'] * 0.97, 2),
                'stop': round(last['BB_UPPER'] * 1.03, 2),
                'reason': f"Bollinger squeeze breakdown. RSI {last['RSI']:.0f}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': round(last['VOL_RATIO'], 1),
                'strategy': self.name,
            })

        return signals
