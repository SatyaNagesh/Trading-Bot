import pandas as pd
import pandas_ta as ta


class EMAStrategy:
    name = 'ema_crossover'
    display = 'Trend Pullback'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 250:
            return []
        df = df.copy()
        slow = params['ema_slow']
        trend = params['ema_trend']
        rsi_p = params['rsi_period']
        vol_period = params['volume_sma_period']

        df['EMA_SLOW'] = ta.ema(df['Close'], length=slow)
        df['EMA_TREND'] = ta.ema(df['Close'], length=trend)
        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['EMA_SLOW']) or pd.isna(last['EMA_TREND']):
            return []

        above_both = last['Close'] > last['EMA_SLOW'] and last['Close'] > last['EMA_TREND']
        below_both = last['Close'] < last['EMA_SLOW'] and last['Close'] < last['EMA_TREND']

        ema_slope_bull = last['EMA_SLOW'] > df['EMA_SLOW'].iloc[-5] if len(df) >= 5 else True
        ema_slope_bear = last['EMA_SLOW'] < df['EMA_SLOW'].iloc[-5] if len(df) >= 5 else True

        near_slow = abs(last['Close'] - last['EMA_SLOW']) / last['EMA_SLOW'] < 0.008

        if above_both and ema_slope_bull and near_slow:
            if prev['Close'] <= prev['EMA_SLOW'] * 1.005 and last['Close'] > last['EMA_SLOW']:
                if last['RSI'] > 55 and last['RSI'] < 70:
                    signals.append({
                        'type': 'BUY',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 1.04, 2),
                        'stop': round(last['Close'] * 0.985, 2),
                        'reason': f"Trend pullback bounce at {slow} EMA (slope up), RSI {last['RSI']:.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        elif below_both and ema_slope_bear and near_slow:
            if prev['Close'] >= prev['EMA_SLOW'] * 0.995 and last['Close'] < last['EMA_SLOW']:
                if last['RSI'] < 50 and last['RSI'] > 30:
                    signals.append({
                        'type': 'SELL',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 0.96, 2),
                        'stop': round(last['Close'] * 1.02, 2),
                        'reason': f"Trend rejection at {slow} EMA (slope down), RSI {last['RSI']:.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        return signals
