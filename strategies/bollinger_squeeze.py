import pandas as pd
import pandas_ta as ta


class BollingerStrategy:
    name = 'bollinger_squeeze'
    display = 'Volume Breakout'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 50:
            return []
        df = df.copy()
        vol_period = params['volume_sma_period']
        vol_thresh = params['volume_threshold']

        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']
        df['RSI'] = ta.rsi(df['Close'], length=params['rsi_period'])
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()

        mid = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std(ddof=0)
        df['BB_UPPER'] = mid + 2.0 * std
        df['BB_LOWER'] = mid - 2.0 * std

        df['HIGH_20'] = df['Close'].rolling(window=20).max()
        df['LOW_20'] = df['Close'].rolling(window=20).min()
        df['EMA_50'] = ta.ema(df['Close'], length=50)

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['VOL_RATIO']) or pd.isna(last['HIGH_20']):
            return []

        above_trend = pd.isna(last['SMA_200']) or last['Close'] > last['SMA_200']
        below_trend = pd.isna(last['SMA_200']) or last['Close'] < last['SMA_200']
        high_vol = last['VOL_RATIO'] > vol_thresh
        ema50_slope = (last['EMA_50'] - df['EMA_50'].iloc[-5]) / df['EMA_50'].iloc[-5] if len(df) >= 5 else 0

        if above_trend and high_vol and ema50_slope > 0 and last['Close'] > last['HIGH_20'] * 0.99:
            if prev['Close'] <= prev['HIGH_20'] * 0.99:
                if last['RSI'] < 75:
                    signals.append({
                        'type': 'BUY',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] + last['ATR'] * 2, 2),
                        'stop': round(last['Close'] - last['ATR'] * 0.8, 2),
                        'reason': f"Volume {last['VOL_RATIO']:.1f}x breakout above 20d range",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        elif below_trend and high_vol and ema50_slope < 0 and last['Close'] < last['LOW_20'] * 1.01:
            if prev['Close'] >= prev['LOW_20'] * 1.01:
                if last['RSI'] > 25:
                    signals.append({
                        'type': 'SELL',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] - last['ATR'] * 2, 2),
                        'stop': round(last['Close'] + last['ATR'] * 0.8, 2),
                        'reason': f"Volume {last['VOL_RATIO']:.1f}x breakdown below 20d range",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        return signals
