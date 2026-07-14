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
        vol_thresh = params['volume_threshold']
        adx_p = params['adx_period']
        adx_t = params['adx_threshold']

        df['RSI'] = ta.rsi(df['Close'], length=rsi_p)
        mid = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std(ddof=0)
        df['BB_UPPER'] = mid + 2.0 * std
        df['BB_LOWER'] = mid - 2.0 * std
        df['VOL_SMA'] = df['Volume'].rolling(window=vol_period).mean()
        df['VOL_RATIO'] = df['Volume'] / df['VOL_SMA']
        df['SMA_50'] = df['Close'].rolling(window=50).mean()

        adx = ta.adx(df['High'], df['Low'], df['Close'], length=adx_p)
        if adx is not None:
            df['ADX'] = adx[f'ADX_{adx_p}']

        signals = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last['RSI']):
            return []

        if 'ADX' in df.columns and (pd.isna(last['ADX']) or last['ADX'] > 30):
            return []

        if last['RSI'] < rsi_os and prev['RSI'] >= rsi_os:
            if pd.isna(last['BB_LOWER']):
                return []
            near_bb = last['Close'] <= last['BB_LOWER'] * 1.015
            if near_bb and last['Close'] > last['SMA_50'] * 0.97:
                vol_ok = last['VOL_RATIO'] > vol_thresh
                vol_note = f" + Vol {last['VOL_RATIO']:.1f}x" if vol_ok else ""
                signals.append({
                    'type': 'BUY',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 1.04, 2),
                    'stop': round(last['Close'] * 0.98, 2),
                    'reason': f"RSI oversold bounce {last['RSI']:.0f} at BB lower{vol_note}",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        elif last['RSI'] > rsi_ob and prev['RSI'] <= rsi_ob:
            if pd.isna(last['BB_UPPER']):
                return []
            near_bb = last['Close'] >= last['BB_UPPER'] * 0.985
            if near_bb:
                signals.append({
                    'type': 'SELL',
                    'price': round(last['Close'], 2),
                    'target': round(last['Close'] * 0.96, 2),
                    'stop': round(last['Close'] * 1.02, 2),
                    'reason': f"RSI overbought reversal {last['RSI']:.0f} at BB upper",
                    'rsi': round(last['RSI'], 1),
                    'volume_ratio': round(last['VOL_RATIO'], 1),
                    'strategy': self.name,
                })

        return signals
