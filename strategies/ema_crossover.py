import pandas as pd
import pandas_ta as ta


class EMAStrategy:
    name = 'ema_crossover'
    display = 'EMA Crossover'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < max(params['ema_trend'], 250):
            return []
        df = df.copy()
        fast = params['ema_fast']
        slow = params['ema_slow']
        trend = params['ema_trend']
        rsi_p = params['rsi_period']
        rsi_ob = params['rsi_overbought']
        rsi_os = params['rsi_oversold']
        vol_period = params['volume_sma_period']
        vol_thresh = params['volume_threshold']
        adx_p = params['adx_period']
        adx_t = params['adx_threshold']

        df['EMA_FAST'] = ta.ema(df['Close'], length=fast)
        df['EMA_SLOW'] = ta.ema(df['Close'], length=slow)
        df['EMA_TREND'] = ta.ema(df['Close'], length=trend)
        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']

        adx = ta.adx(df['High'], df['Low'], df['Close'], length=adx_p)
        if adx is not None:
            df['ADX'] = adx[f'ADX_{adx_p}']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]
        p3 = df.iloc[-3]

        if pd.isna(last['EMA_FAST']) or pd.isna(last['EMA_SLOW']) or pd.isna(last['EMA_TREND']):
            return []

        if 'ADX' in df.columns and (pd.isna(last['ADX']) or last['ADX'] < adx_t):
            return []

        if last['Close'] < last['EMA_TREND'] * 0.95:
            return []

        if prev['EMA_FAST'] <= prev['EMA_SLOW'] and last['EMA_FAST'] > last['EMA_SLOW']:
            if last['RSI'] < rsi_ob and last['RSI'] > 40:
                vol_ok = last['VOL_RATIO'] > vol_thresh
                vol_note = f" + Volume {last['VOL_RATIO']:.1f}x" if vol_ok else ""
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 1.05, 2),
                    'stop': round(last['Close'] * 0.975, 2),
                    'reason': f"EMA {fast}/{slow} bullish cross above {trend} MA{vol_note}, ADX {last.get('ADX', 0):.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        elif prev['EMA_FAST'] >= prev['EMA_SLOW'] and last['EMA_FAST'] < last['EMA_SLOW']:
            if last['RSI'] > rsi_os and last['RSI'] < 60:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 0.95, 2),
                    'stop': round(last['Close'] * 1.025, 2),
                    'reason': f"EMA {fast}/{slow} bearish cross, ADX {last.get('ADX', 0):.0f}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        return signals
