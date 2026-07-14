from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

_supabase = None


def get_db():
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def log_signal(stock: str, signal_type: str, price: float, target: float,
               stop_loss: float, rsi: float, volume_ratio: float, reason: str,
               strategies: list = None, votes: int = None):
    try:
        data = {
            'stock': stock,
            'signal_type': signal_type,
            'price': price,
            'target': target,
            'stop_loss': stop_loss,
            'rsi': rsi,
            'volume_ratio': volume_ratio,
            'reason': reason,
            'strategies': strategies or [],
            'votes': votes or 1,
        }
        get_db().table('trading_signals').insert(data).execute()
    except Exception:
        pass


def log_trade(ticker: str, trade_type: str, entry_price: float, exit_price: float = None,
              pnl_pct: float = None, strategy: str = ''):
    try:
        data = {
            'stock': ticker,
            'signal_type': trade_type,
            'price': entry_price,
            'target': exit_price or 0,
            'reason': f"Paper trade: {strategy}" if strategy else "Paper trade",
        }
        if pnl_pct is not None:
            data['pnl_pct'] = pnl_pct
        get_db().table('trading_signals').insert(data).execute()
    except Exception:
        pass


def get_recent_signals(stock: str, signal_type: str = None, limit: int = 5) -> list:
    try:
        q = get_db().table('trading_signals') \
            .select('*') \
            .eq('stock', stock) \
            .order('created_at', desc=True) \
            .limit(limit)
        if signal_type:
            q = q.eq('signal_type', signal_type)
        resp = q.execute()
        return resp.data or []
    except Exception:
        return []


def is_duplicate(stock: str, signal_type: str) -> bool:
    recent = get_recent_signals(stock, signal_type, limit=1)
    return len(recent) > 0
