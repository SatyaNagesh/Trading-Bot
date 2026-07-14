import requests


def send_signal(signal_type: str, stock: str, price: float, target: float,
                stop_loss: float, reason: str, rsi: float, volume_ratio: float,
                votes: int = None, strategies: list = None, webhook_url: str = ''):
    if not webhook_url:
        return False

    color_map = {'BUY': 0x00ff00, 'SELL': 0xff0000, 'WATCH': 0xffaa00}
    emoji_map = {'BUY': '🟢', 'SELL': '🔴', 'WATCH': '🟡'}
    rr = round((target - price) / (price - stop_loss), 1) if price != stop_loss else 0

    fields = [
        {'name': 'Current', 'value': f"₹{price:,.2f}", 'inline': True},
        {'name': 'Target', 'value': f"₹{target:,.2f}", 'inline': True},
        {'name': 'Stop Loss', 'value': f"₹{stop_loss:,.2f}", 'inline': True},
        {'name': 'Risk/Reward', 'value': f"1:{rr}", 'inline': True},
        {'name': 'RSI (14)', 'value': f"{rsi:.0f}", 'inline': True},
        {'name': 'Volume', 'value': f"{volume_ratio:.1f}x avg", 'inline': True},
    ]

    if votes is not None:
        fields.insert(0, {'name': 'Strategy Vote', 'value': f"{votes}/4 strategies", 'inline': True})
    if strategies:
        fields.append({'name': 'Triggered By', 'value': ', '.join(strategies), 'inline': False})

    fields.append({
        'name': 'Analysis',
        'value': reason,
        'inline': False,
    })
    fields.append({
        'name': 'Chart',
        'value': f"[View on TradingView](https://www.tradingview.com/chart/?symbol=NSE:{stock.replace('.NS', '')})",
        'inline': False,
    })

    payload = {
        'embeds': [{
            'title': f"{emoji_map[signal_type]} {signal_type}  {stock.replace('.NS', '')}",
            'color': color_map[signal_type],
            'fields': fields,
            'footer': {'text': 'Multi-Strategy AI • Verify before trading'},
        }]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 204
    except requests.RequestException:
        return False


def send_report(webhook_url: str, title: str, lines: list, color: int = 0x3498db):
    if not webhook_url:
        return
    payload = {
        'embeds': [{
            'title': title,
            'color': color,
            'description': '\n'.join(lines),
        }]
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except requests.RequestException:
        pass


def send_error(webhook_url: str, message: str):
    payload = {
        'embeds': [{
            'title': '⚠️ Bot Alert',
            'color': 0xe74c3c,
            'description': message,
        }]
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except requests.RequestException:
        pass
