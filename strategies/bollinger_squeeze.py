import pandas as pd
import pandas_ta as ta


class BollingerStrategy:
    name = 'bollinger_squeeze'
    display = 'Bollinger Squeeze'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()
        bb_p = params['bb_period']
        bb_s = params['bb_std']
        adx_p = params['adx_period']
        adx_t = params['adx_threshold']

        mid = df['Close'].rolling(bb_p).mean()
        std = df['Close'].rolling(bb_p).std(ddof=0)
        df['BB_UPPER'] = mid + bb_s * std
        df['BB_MID'] = mid
        df['BB_LOWER'] = mid - bb_s * std
        df['BB_WIDTH'] = (df['BB_UPPER'] - df['BB_LOWER']) / df['BB_MID']
        df['BB_PCT'] = (df['Close'] - df['BB_LOWER']) / (df['BB_UPPER'] - df['BB_LOWER'])
        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])
        df['VOL_SMA'] = df['Volume'].rolling(window=20).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        adx = ta.adx(df['High'], df['Low'], df['Close'], length=adx_p)
        if adx is not None:
            df['ADX'] = adx[f'ADX_{adx_p}']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        p3 = df.iloc[-3]

        if pd.isna(last['BB_WIDTH']):
            return []

        width_avg = df['BB_WIDTH'].rolling(window=20).mean()
        widths_20 = df['BB_WIDTH'].tail(20)
        width_rank = (widths_20.rank(pct=True).iloc[-1] if len(widths_20) > 0 else 0.5)

        squeeze_active = (
            last['BB_WIDTH'] < width_avg.iloc[-1] * 0.7
            and width_rank < 0.25
        )

        squeeze_persistent = (
            df['BB_WIDTH'].iloc[-3] < width_avg.iloc[-3] * 0.8
            and df['BB_WIDTH'].iloc[-2] < width_avg.iloc[-2] * 0.8
        )

        if not (squeeze_active and squeeze_persistent):
            return []

        if 'ADX' in df.columns and (pd.isna(last['ADX']) or last['ADX'] < adx_t - 5):
            return []

        if last['BB_PCT'] > 0.92 and prev['BB_PCT'] <= 0.85 and last['VOL_RATIO'] > 1.5:
            if last['RSI'] < 70:
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['BB_UPPER'] * 1.025, 2),
                    'stop': round(last['BB_MID'] * 0.985, 2),
                    'reason': f"BB squeeze breakout up, Vol {last['VOL_RATIO']:.1f}x, ADX {last.get('ADX', 0):.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        elif last['BB_PCT'] < 0.08 and prev['BB_PCT'] >= 0.15 and last['VOL_RATIO'] > 1.5:
            if last['RSI'] > 30:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['BB_LOWER'] * 0.975, 2),
                    'stop': round(last['BB_MID'] * 1.015, 2),
                    'reason': f"BB squeeze breakdown, Vol {last['VOL_RATIO']:.1f}x, ADX {last.get('ADX', 0):.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        return signals
