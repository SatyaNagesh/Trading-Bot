import pandas as pd
import pandas_ta as ta


class RSIStrategy:
    name = 'rsi_reversal'
    display = 'RSI Reversal'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()
        rsi_p = params['rsi_period']
        rsi_ob = params['rsi_overbought']
        rsi_os = params['rsi_oversold']
        vol_period = params['volume_sma_period']

        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        mid = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std(ddof=0)
        df['BB_UPPER'] = mid + 2.0 * std
        df['BB_LOWER'] = mid - 2.0 * std
        df['BB_MID'] = mid
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']
        df['SMA_200'] = df['Close'].rolling(window=200).mean()

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['RSI']) or pd.isna(last['BB_LOWER']):
            return []

        if last['RSI'] < rsi_os and prev['RSI'] >= rsi_os:
            near_bb = last['Close'] <= last['BB_LOWER'] * 1.01
            above_200 = pd.isna(last['SMA_200']) or last['Close'] > last['SMA_200'] * 0.95
            if near_bb and above_200:
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['BB_MID'], 2),
                    'stop': round(last['BB_LOWER'] * 0.99, 2),
                    'reason': f"RSI oversold {last['RSI']:.0f} at BB lower, mean reversion to mid",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        elif last['RSI'] > rsi_ob and prev['RSI'] <= rsi_ob:
            near_bb = last['Close'] >= last['BB_UPPER'] * 0.99
            if near_bb:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['BB_MID'], 2),
                    'stop': round(last['BB_UPPER'] * 1.01, 2),
                    'reason': f"RSI overbought {last['RSI']:.0f} at BB upper, mean reversion to mid",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        return signals
