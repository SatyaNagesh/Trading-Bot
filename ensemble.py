import pandas as pd

from strategies import STRATEGIES, STRATEGY_REGIMES


def vote(df: pd.DataFrame, params: dict, regime: str = None) -> list[dict]:
    min_votes = params.get('min_votes', 2)
    require_regime = params.get('require_regime_match', True)

    all_signals = []
    for name, strategy in STRATEGIES.items():
        if require_regime and regime and regime != 'unknown':
            allowed = STRATEGY_REGIMES.get(name, [])
            if regime not in allowed:
                continue
        signals = strategy.run(df, {})
        all_signals.extend(signals)

    buy_signals = [s for s in all_signals if s['type'] == 'BUY']
    sell_signals = [s for s in all_signals if s['type'] == 'SELL']

    results = []
    for group, sig_type in [(buy_signals, 'BUY'), (sell_signals, 'SELL')]:
        if not group:
            continue

        best = max(group, key=lambda x: abs(x['price'] - x['target']))
        strategies_agree = [s['strategy'] for s in group]
        avg_rsi = sum(s['rsi'] for s in group if s['rsi']) / max(len([s for s in group if s['rsi']]), 1)
        avg_vol = sum(s['volume_ratio'] for s in group if s['volume_ratio']) / max(len([s for s in group if s['volume_ratio']]), 1)

        results.append({
            'type': sig_type,
            'price': best['price'],
            'target': best['target'],
            'stop': best['stop'],
            'votes': len(group),
            'strategies': strategies_agree,
            'avg_rsi': round(avg_rsi, 1),
            'avg_volume_ratio': round(avg_vol, 1),
            'reason': f"{len(group)}/{len(STRATEGIES)} strategies agree: {', '.join(strategies_agree)}",
        })

    return [r for r in results if r['votes'] >= min_votes]


def run_all_strategies(df: pd.DataFrame, params: dict) -> list[dict]:
    all_signals = []
    for name, strategy in STRATEGIES.items():
        signals = strategy.run(df, {})
        all_signals.extend(signals)
    return all_signals
