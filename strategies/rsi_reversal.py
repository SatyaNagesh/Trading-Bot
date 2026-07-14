import pandas as pd
import pandas_ta as ta


class RSIStrategy:
    name = 'rsi_reversal'
    display = 'RSI Reversal'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 30:
            return []
        df = df.copy()
        rsi_p = params['rsi_period']
        rsi_ob = params['rsi_overbought']
        rsi_os = params['rsi_oversold']
        vol_period = params['volume_sma_period']
        vol_thresh = params['volume_threshold']

        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        df['BB_UPPER'] = df['Close'].rolling(window=20).mean() + 2 * df['Close'].rolling(window=20).std()
        df['BB_LOWER'] = df['Close'].rolling(window=20).mean() - 2 * df['Close'].rolling(window=20).std()
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['RSI']):
            return []

        if last['RSI'] < rsi_os and prev['RSI'] >= rsi_os:
            vol_note = f" + Volume {last['VOL_RATIO']:.1f}x" if last['VOL_RATIO'] > vol_thresh else ""
            near_bb = " near BB lower" if last['Close'] <= last['BB_LOWER'] * 1.02 else ""
            signals.append({
                'type': 'BUY',
                'price': round(last['Close'], 2),
                'target': round(last['Close'] * 1.06, 2),
                'stop': round(last['Close'] * 0.95, 2),
                'reason': f"RSI oversold bounce ({last['RSI']:.0f}→{rsi_os})+{near_bb}{vol_note}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': round(last['VOL_RATIO'], 1),
                'strategy': self.name,
            })

        elif last['RSI'] > rsi_ob and prev['RSI'] <= rsi_ob:
            near_bb = " near BB upper" if last['Close'] >= last['BB_UPPER'] * 0.98 else ""
            signals.append({
                'type': 'SELL',
                'price': round(last['Close'], 2),
                'target': round(last['Close'] * 0.94, 2),
                'stop': round(last['Close'] * 1.06, 2),
                'reason': f"RSI overbought reversal ({last['RSI']:.0f}→{rsi_ob}){near_bb}",
                'rsi': round(last['RSI'], 1),
                'volume_ratio': round(last['VOL_RATIO'], 1),
                'strategy': self.name,
            })

        return signals
