import pandas as pd
import pandas_ta as ta


class EMAStrategy:
    name = 'ema_crossover'
    display = 'EMA Crossover'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()
        fast = params['ema_fast']
        slow = params['ema_slow']
        rsi_p = params['rsi_period']
        rsi_ob = params['rsi_overbought']
        rsi_os = params['rsi_oversold']
        vol_period = params['volume_sma_period']
        vol_thresh = params['volume_threshold']

        df['EMA_FAST'] = ta.ema(df['Close'], length=fast)
        df['EMA_SLOW'] = ta.ema(df['Close'], length=slow)
        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['EMA_FAST']) or pd.isna(last['EMA_SLOW']):
            return []

        if prev['EMA_FAST'] <= prev['EMA_SLOW'] and last['EMA_FAST'] > last['EMA_SLOW']:
            if last['RSI'] < rsi_ob:
                vol = f" + Volume {last['VOL_RATIO']:.1f}x" if last['VOL_RATIO'] > vol_thresh else ""
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 1.08, 2),
                    'stop': round(last['Close'] * 0.96, 2),
                    'reason': f"EMA {fast}/{slow} bullish crossover{vol}, RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        elif prev['EMA_FAST'] >= prev['EMA_SLOW'] and last['EMA_FAST'] < last['EMA_SLOW']:
            if last['RSI'] > rsi_os:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 0.92, 2),
                    'stop': round(last['Close'] * 1.04, 2),
                    'reason': f"EMA {fast}/{slow} bearish crossover, RSI {last['RSI']:.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        return signals
