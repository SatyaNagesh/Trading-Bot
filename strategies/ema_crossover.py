import pandas as pd
import pandas_ta as ta


class EMAStrategy:
    name = 'ema_crossover'
    display = 'Trend Pullback'

    def run(self, df: pd.DataFrame, params: dict) -> list[dict]:
        if df is None or len(df) < 250:
            return []
        df = df.copy()
        fast = params['ema_fast']
        slow = params['ema_slow']
        trend = params['ema_trend']
        rsi_p = params['rsi_period']
        vol_period = params['volume_sma_period']
        adx_p = params['adx_period']

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

        if pd.isna(last['EMA_FAST']) or pd.isna(last['EMA_TREND']):
            return []

        above_trend = last['Close'] > last['EMA_TREND']
        below_trend = last['Close'] < last['EMA_TREND']

        near_slow = abs(last['Close'] - last['EMA_SLOW']) / last['EMA_SLOW'] < 0.01
        adx_ok = 'ADX' not in df.columns or (not pd.isna(last['ADX']) and last['ADX'] > 20)

        if above_trend and near_slow and adx_ok:
            if prev['Close'] <= prev['EMA_SLOW'] and last['Close'] > last['EMA_SLOW']:
                if 40 <= last['RSI'] <= 60:
                    vol_note = f" Vol {last['VOL_RATIO']:.1f}x" if last['VOL_RATIO'] > 1.2 else ""
                    signals.append({
                        'type': 'BUY',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 1.03, 2),
                        'stop': round(last['Close'] * 0.985, 2),
                        'reason': f"Trend pullback bounce at {slow} EMA{vol_note}, ADX {last.get('ADX', 0):.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        elif below_trend and near_slow and adx_ok:
            if prev['Close'] >= prev['EMA_SLOW'] and last['Close'] < last['EMA_SLOW']:
                if 40 <= last['RSI'] <= 60:
                    signals.append({
                        'type': 'SELL',
                        'price': round(last['Close'], 2),
                        'target': round(last['Close'] * 0.97, 2),
                        'stop': round(last['Close'] * 1.015, 2),
                        'reason': f"Trend pullback rejection at {slow} EMA, ADX {last.get('ADX', 0):.0f}",
                        'rsi': round(last['RSI'], 1),
                        'volume_ratio': round(last['VOL_RATIO'], 1),
                        'strategy': self.name,
                    })

        return signals
