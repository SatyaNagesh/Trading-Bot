"""Strategy templates — composable building blocks for candidate strategies."""

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from packages.domain.models import Bar, Signal, SignalDirection, MarketContext
from packages.indicators.signals import SignalGenerator


IndicatorFn = Callable[[pd.DataFrame], pd.Series]


def sma(period: int) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(period).mean()

    return fn


def ema(period: int) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=period, adjust=False).mean()

    return fn


def rsi(period: int = 14) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    return fn


def macd(fast: int = 12, slow: int = 26, signal: int = 9) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        f = df["close"].ewm(span=fast, adjust=False).mean()
        s = df["close"].ewm(span=slow, adjust=False).mean()
        return f - s

    return fn


def bollinger_band(period: int = 20, std_dev: float = 2.0) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        mid = df["close"].rolling(period).mean()
        std = df["close"].rolling(period).std()
        return (df["close"] - mid) / std.replace(0, 1e-10)

    return fn


def atr(period: int = 14) -> IndicatorFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)
        tr1 = high - low
        tr2 = (high - close).abs()
        tr3 = (low - close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    return fn


INDICATOR_FACTORIES: dict[str, Callable[..., IndicatorFn]] = {
    "sma": sma,
    "ema": ema,
    "rsi": rsi,
    "macd": macd,
    "bollinger": bollinger_band,
    "atr": atr,
}


@dataclass
class IndicatorTemplate:
    name: str
    factory: str
    params: dict = field(default_factory=dict)

    def build(self) -> IndicatorFn:
        fn = INDICATOR_FACTORIES[self.factory]
        return fn(**self.params)


@dataclass
class EntryRuleTemplate:
    indicator_a: str
    operator: str
    indicator_b: str | None = None
    threshold: float | None = None

    def build(self, indicator_map: dict[str, IndicatorFn]) -> Callable:
        def entry_fn(values: dict[str, float]) -> SignalDirection | None:
            a = values.get(self.indicator_a, 0)
            b = values.get(self.indicator_b, 0) if self.indicator_b else (self.threshold or 0)
            if self.operator == ">" and a > b:
                return SignalDirection.LONG
            if self.operator == "<" and a < b:
                return SignalDirection.SHORT
            if self.operator == "cross_above" and a > b:
                return SignalDirection.LONG
            if self.operator == "cross_below" and a < b:
                return SignalDirection.SHORT
            if self.operator == "above" and a > b:
                return SignalDirection.LONG
            if self.operator == "below" and a < b:
                return SignalDirection.SHORT
            return None

        return entry_fn


@dataclass
class ExitTemplate:
    take_profit_pct: float = 0.0
    stop_loss_pct: float = 0.0
    trailing_stop_pct: float = 0.0
    max_bars_hold: int = 0


@dataclass
class StrategyTemplate:
    id: str
    name: str
    indicators: list[IndicatorTemplate] = field(default_factory=list)
    entry: EntryRuleTemplate | None = None
    exit: ExitTemplate = field(default_factory=ExitTemplate)
    description: str = ""

    def build_signal_fn(self) -> Callable[[Bar, MarketContext], list[Signal]]:
        indicator_fns = {t.name: t.build() for t in self.indicators}
        entry_fn = (
            self.entry.build({k: lambda v=v: v for k, v in indicator_fns.items()})
            if self.entry
            else None
        )
        sig_gen = SignalGenerator(self.id)

        def signal_fn(bar: Bar, ctx: MarketContext) -> list[Signal]:
            _ = ctx
            return [sig_gen.neutral()]

        if self.entry:
            price_data = None

            def signal_fn(bar: Bar, ctx: MarketContext) -> list[Signal]:
                nonlocal price_data
                if (
                    price_data is None
                    and hasattr(ctx, "indicator_df")
                    and ctx.indicator_df is not None
                ):
                    price_data = ctx.indicator_df
                values = {}
                for name, fn in indicator_fns.items():
                    try:
                        if price_data is not None:
                            values[name] = float(fn(price_data).iloc[-1])
                        else:
                            values[name] = 0.0
                    except (IndexError, ValueError, TypeError):
                        values[name] = 0.0
                direction = entry_fn(values)
                if direction == SignalDirection.LONG:
                    return [sig_gen.long(confidence=0.6, reason=[self.description])]
                if direction == SignalDirection.SHORT:
                    return [sig_gen.short(confidence=0.6, reason=[self.description])]
                return [sig_gen.neutral()]

        return signal_fn

    def precompute_indicators(self, bars: list[Bar]) -> pd.DataFrame:
        df = pd.DataFrame(
            [
                {
                    "close": float(b.close),
                    "high": float(b.high),
                    "low": float(b.low),
                    "open": float(b.open),
                    "volume": b.volume,
                    "timestamp": b.timestamp,
                }
                for b in bars
            ]
        )
        for t in self.indicators:
            try:
                fn = t.build()
                df[t.name] = fn(df)
            except Exception:
                df[t.name] = 0.0
        return df
