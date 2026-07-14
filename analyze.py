import yfinance as yf
import sys
from datetime import datetime, timezone

from config import WATCHLIST, INDICATOR_PARAMS, DISCORD_WEBHOOK_URL
from regime import detect_regime, REGIME_PARAMS
from ensemble import vote
from notify import send_signal, send_error, send_report
from db import log_signal, is_duplicate


def fetch_stock(ticker: str) -> tuple:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1mo', interval='1h')
        if hist.empty:
            return None, None
        info = stock.info
        name = info.get('shortName') or info.get('longName') or ticker
        return hist, name
    except Exception:
        return None, None


def main():
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    print(f"[{now.isoformat()}] Starting multi-strategy analysis...")

    signals_fired = 0
    for ticker in WATCHLIST:
        hist, name = fetch_stock(ticker)
        if hist is None:
            print(f"  {ticker}: skipped (no data)")
            continue

        ticker_name = name or ticker
        regime = detect_regime(hist, REGIME_PARAMS)
        confidence = 0

        from regime import regime_confidence
        confidence = regime_confidence(hist, regime)
        print(f"  {ticker_name}: regime={regime} (confidence={confidence:.0%})")

        ensemble_signals = vote(hist, {}, regime=regime)

        if not ensemble_signals:
            print(f"  {ticker_name}: no ensemble signal")
            continue

        for sig in ensemble_signals:
            if is_duplicate(ticker, sig['type']):
                print(f"  {ticker_name}: {sig['type']} — duplicate, skipped")
                continue

            ok = send_signal(
                signal_type=sig['type'],
                stock=ticker,
                price=sig['price'],
                target=sig['target'],
                stop_loss=sig['stop'],
                reason=sig['reason'],
                rsi=sig['avg_rsi'],
                volume_ratio=sig['avg_volume_ratio'],
                votes=sig['votes'],
                strategies=sig['strategies'],
                webhook_url=DISCORD_WEBHOOK_URL,
            )
            log_signal(
                stock=ticker,
                signal_type=sig['type'],
                price=sig['price'],
                target=sig['target'],
                stop_loss=sig['stop'],
                rsi=sig['avg_rsi'],
                volume_ratio=sig['avg_volume_ratio'],
                reason=sig['reason'],
                strategies=sig['strategies'],
                votes=sig['votes'],
            )
            signals_fired += 1
            status = "sent" if ok else "failed"
            print(f"  {ticker_name}: {sig['type']} ({sig['votes']}/4 votes) @ ₹{sig['price']} — {status}")

    if signals_fired == 0:
        print("  No signals fired across all stocks.")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Done. {signals_fired} signal(s).")


if __name__ == '__main__':
    main()
