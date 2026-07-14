import numpy as np
import pandas as pd


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 0
    r = avg_win / avg_loss
    kelly = win_rate - ((1 - win_rate) / r)
    return max(0, kelly)


def position_size(equity: float, risk_per_trade: float, stop_loss_pct: float,
                  kelly_fraction: float = 0.25) -> tuple[float, float]:
    base = equity * risk_per_trade
    if stop_loss_pct <= 0:
        return 0, 0
    units = base / stop_loss_pct
    capped = min(units, equity * kelly_fraction)
    return round(capped, 2), round(capped / equity * 100, 2)


def max_drawdown(equity_curve: pd.Series) -> dict:
    peak = equity_curve.expanding().max()
    dd = (equity_curve - peak) / peak
    return {
        'max_drawdown_pct': round(dd.min() * 100, 2),
        'max_drawdown_duration': int((dd < 0).sum()),
    }


def volatility_scaling(returns: pd.Series, target_vol: float = 0.15) -> float:
    recent_vol = returns.tail(20).std() * np.sqrt(252)
    if recent_vol == 0:
        return 1.0
    scale = target_vol / recent_vol
    return max(0.1, min(scale, 2.0))


def calculate_sharpe(returns: pd.Series, risk_free: float = 0.065) -> float:
    excess = returns - risk_free / 252
    if returns.std() == 0:
        return 0
    return round(np.sqrt(252) * excess.mean() / returns.std(), 2)


def calculate_sortino(returns: pd.Series, risk_free: float = 0.065) -> float:
    excess = returns - risk_free / 252
    downside = returns[returns < 0].std()
    if downside == 0:
        return 0
    return round(np.sqrt(252) * excess.mean() / downside, 2)


def calculate_calmar(returns: pd.Series, equity_curve: pd.Series) -> float:
    ann_return = (1 + returns.mean()) ** 252 - 1
    dd = max_drawdown(equity_curve)['max_drawdown_pct']
    if dd == 0:
        return 0
    return round(ann_return / abs(dd) * 100, 2)
