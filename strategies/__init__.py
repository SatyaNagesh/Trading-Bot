from .ema_crossover import EMAStrategy
from .rsi_reversal import RSIStrategy
from .macd_divergence import MACDStrategy
from .bollinger_squeeze import BollingerStrategy

STRATEGIES = {
    'ema_crossover': EMAStrategy(),
    'rsi_reversal': RSIStrategy(),
    'macd_divergence': MACDStrategy(),
    'bollinger_squeeze': BollingerStrategy(),
}

STRATEGY_REGIMES = {
    'ema_crossover': ['bullish_trend', 'bearish_trend'],
    'rsi_reversal': ['sideways', 'mixed'],
    'macd_divergence': ['bullish_trend', 'bearish_trend', 'mixed'],
    'bollinger_squeeze': ['high_volatility', 'sideways'],
}
