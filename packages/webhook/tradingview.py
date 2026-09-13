"""TradingView webhook ingestion — validated, idempotent, PAPER-ONLY signal source.

A TradingView alert is an EXTERNAL SIGNAL SOURCE. It can never place an order
directly. Every accepted event is converted into a ``Signal`` + ``Bar`` and
pushed through the EXISTING paper path via :meth:`PaperTradingLoop.process_signal`
(the same path used by ``POST /trading/manual``):

    TradingView event
      -> validation layer (this module)
      -> PaperTradingLoop.process_signal
          -> session gate -> health gate -> OMS sizing
          -> RiskEngine.check_order -> OMS.validate
          -> ExecutionEngine.execute -> PaperBroker
          -> PortfolioEngine -> TradeJournal

No second execution path is created, and no broker is ever touched directly.

Fail-closed guarantees enforced here:
  * No webhook without an explicit operator secret  -> NOT_CONFIGURED
  * Refuses to run if the loop's broker is live-capable -> PAPER_GUARD
  * Unknown/duplicate/stale/future/malformed events never reach the loop
  * Outside the instrument session -> REJECTED_OUTSIDE_SESSION (no phantom trade)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from packages.core.exceptions import ConfigurationError
from packages.core.logging import get_logger
from packages.domain.models import Bar, Signal, SignalDirection
from packages.session.manager import SessionManager, SessionStatus
from packages.trading.loop import PaperTradingLoop

logger = get_logger("tradingview_webhook")

# -- Env keys (fail-closed: no hard-coded credentials) ------------------------
ENV_SECRET = "QUANTLAB_WEBHOOK_SECRET"
ENV_MAX_STALE_SECONDS = "QUANTLAB_WEBHOOK_MAX_STALE_SECONDS"
ENV_FUTURE_SKEW_SECONDS = "QUANTLAB_WEBHOOK_FUTURE_SKEW_SECONDS"
ENV_CONFIDENCE = "QUANTLAB_WEBHOOK_CONFIDENCE"
ENV_KNOWN_SYMBOLS = "QUANTLAB_WEBHOOK_KNOWN_SYMBOLS"
ENV_24_7_SYMBOLS = "QUANTLAB_WEBHOOK_24_7_SYMBOLS"
ENV_LEDGER_DIR = "QUANTLAB_WEBHOOK_LEDGER_DIR"

SECRET_HEADER = "X-QuantLab-Webhook-Token"
SECRET_BODY_FIELD = "secret"

ALLOWED_SOURCES = {"tradingview"}
ALLOWED_TIMEFRAMES = {
    "1m", "3m", "5m", "15m", "30m", "45m", "1h", "2h", "4h", "1d", "1w", "1M",
}
ALLOWED_DIRECTIONS = {
    "long": SignalDirection.LONG,
    "buy": SignalDirection.LONG,
    "short": SignalDirection.SHORT,
    "sell": SignalDirection.SHORT,
    "neutral": SignalDirection.NEUTRAL,
}
SYMBOL_RE = re.compile(r"^[A-Z0-9._\-]{1,32}$")

# Ledger seen-id in-memory cap (full history stays on disk).
_MAX_SEEN_IDS = 20_000


@dataclass
class WebhookSettings:
    """Operator configuration. Secret empty => webhook disabled (fail closed)."""

    secret: str = ""
    max_stale_seconds: int = 300
    future_skew_seconds: int = 60
    confidence: float = 0.8
    known_symbols: tuple[str, ...] | None = None
    symbols_24_7: frozenset[str] = frozenset()
    ledger_dir: str = "data/webhook"

    @classmethod
    def from_env(cls) -> "WebhookSettings":
        def _int(key: str, default: int) -> int:
            raw = os.environ.get(key, "").strip()
            try:
                return int(raw)
            except ValueError:
                return default

        def _float(key: str, default: float) -> float:
            raw = os.environ.get(key, "").strip()
            try:
                return float(raw)
            except ValueError:
                return default

        known_raw = os.environ.get(ENV_KNOWN_SYMBOLS, "").strip()
        if known_raw:
            known = tuple(_normalize_symbol(s) for s in known_raw.split(",") if s.strip())
        else:
            known = None

        tv_24_7 = frozenset(
            _normalize_symbol(s)
            for s in os.environ.get(ENV_24_7_SYMBOLS, "").split(",")
            if s.strip()
        )
        return cls(
            secret=os.environ.get(ENV_SECRET, "").strip(),
            max_stale_seconds=_int(ENV_MAX_STALE_SECONDS, cls.max_stale_seconds),
            future_skew_seconds=_int(ENV_FUTURE_SKEW_SECONDS, cls.future_skew_seconds),
            confidence=_float(ENV_CONFIDENCE, cls.confidence),
            known_symbols=known,
            symbols_24_7=tv_24_7,
            ledger_dir=os.environ.get(ENV_LEDGER_DIR, cls.ledger_dir),
        )


class WebhookNotConfigured(ConfigurationError):
    """Webhook secret not set — ingestion disabled."""


class WebhookPaperGuard(ConfigurationError):
    """Webhook refuses to drive a live-capable broker."""


def normalize_timestamp(raw: Any) -> datetime:
    """Parse ISO-8601 or epoch (sec/ms) values into an aware UTC datetime.

    Raises ``ValueError`` on anything unparseable.
    """
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value > 1_000_000_000_000:  # milliseconds
            value /= 1000.0
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(raw, str):
        raise ValueError("timestamp must be a string or number")
    text = raw.strip()
    if text == "":
        raise ValueError("empty timestamp")
    try:
        value = float(text)
        if value > 1_000_000_000_000:
            value /= 1000.0
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except ValueError:
        pass
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_symbol(raw: str) -> str:
    symbol = (raw or "").strip().upper()
    for prefix in ("NSE:", "BSE:", "NSEFO:", "NASDAQ:", "NYSE:", "BINANCE:", "CRYPTO:"):
        if symbol.startswith(prefix):
            symbol = symbol[len(prefix):]
            break
    if symbol and not symbol.endswith(".NS") and not symbol.startswith(("BTC", "ETH", "SOL")):
        symbol += ".NS"
    return symbol


def _default_known_symbols() -> frozenset[str]:
    """Default universe: cached bars + the NSE list used by the data pipeline."""
    known: set[str] = set()
    try:
        from packages.market.data_pipeline import get_available_symbols

        known.update(_normalize_symbol(s) for s in get_available_symbols())
    except Exception:  # noqa: BLE001
        pass
    try:
        cache_dir = Path("data/cache/parquet")
        if cache_dir.exists():
            for p in cache_dir.glob("*.parquet"):
                known.add(_normalize_symbol(p.stem.split("_")[0]))
    except Exception:  # noqa: BLE001
        pass
    try:
        with open("data/genuine_bars.pkl", "rb") as f:
            import pickle

            known.update(_normalize_symbol(s) for s in pickle.load(f).keys())
    except Exception:  # noqa: BLE001
        pass
    return frozenset(s for s in known if s)


class TradingViewEvent:
    """Validated, normalized TradingView event (immutable-ish by convention)."""

    __slots__ = (
        "event_id", "symbol", "timeframe", "direction", "event_time",
        "price", "source", "raw",
    )

    def __init__(
        self,
        event_id: str,
        symbol: str,
        timeframe: str,
        direction: SignalDirection,
        event_time: datetime,
        price: Decimal | None,
        source: str,
        raw: dict[str, Any],
    ):
        self.event_id = event_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.event_time = event_time
        self.price = price
        self.source = source
        self.raw = raw


class _AlwaysOpenSession(SessionManager):
    """Session shim used to carry 24/7 instruments through the loop's gate."""

    def is_open(self, dt=None):
        return True

    def check_session(self, dt=None):
        return SessionStatus.OPEN


class TradingViewEventGateway:
    """Validate + dedupe + gate TradingView events, then feed the paper loop."""

    def __init__(self, settings: WebhookSettings | None = None, loop: PaperTradingLoop | None = None) -> None:
        self.settings = settings or WebhookSettings.from_env()
        if loop is None:
            raise ConfigurationError("TradingViewEventGateway requires a PaperTradingLoop")
        self.loop = loop
        self.session: SessionManager = loop.session
        self.known_symbols = (
            frozenset(self.settings.known_symbols)
            if self.settings.known_symbols
            else _default_known_symbols()
        )
        self._seen_ids: set[str] = set()
        self._ledger = Path(self.settings.ledger_dir) / "events.jsonl"
        self._load_seen_ids()
        self._bypass_lock = asyncio.Lock()  # serializes 24/7 session shim swaps

    # ------------------------------------------------------------------ internals

    def _load_seen_ids(self) -> None:
        try:
            if not self._ledger.exists():
                return
            with self._ledger.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    eid = rec.get("event_id")
                    if eid:
                        self._seen_ids.add(eid)
                        if len(self._seen_ids) > _MAX_SEEN_IDS:
                            break
        except OSError:
            logger.warning("webhook_ledger_unreadable", path=str(self._ledger))

    def _persist(self, record: dict[str, Any]) -> None:
        try:
            self._ledger.parent.mkdir(parents=True, exist_ok=True)
            with self._ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            logger.error("webhook_ledger_write_failed", path=str(self._ledger), error=str(e))

    def _record(
        self,
        status: str,
        event: TradingViewEvent | None,
        reason: str,
        *,
        received_at: datetime | None = None,
        session_status: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "status": status,
            "event_id": event.event_id if event else reason_id(reason),
            "received_at": (received_at or datetime.now(timezone.utc)).isoformat(),
            "source": "tradingview" if event else None,
            "reason": reason,
        }
        if event is not None:
            record["event_time"] = event.event_time.isoformat()
            record["symbol"] = event.symbol
            record["timeframe"] = event.timeframe
            record["direction"] = event.direction.value
            if event.price is not None:
                record["price"] = float(event.price)
        if session_status:
            record["session_status"] = session_status
        if result is not None:
            record["result"] = result
            order_id = result.get("order_id")
            if order_id:
                record["order_id"] = order_id
        self._persist(record)
        return record

    # ------------------------------------------------------------------ public API

    async def handle(
        self,
        payload: dict[str, Any] | None,
        header_secret: str | None = None,
        *,
        received_at: datetime | None = None,
        remote_addr: str | None = None,
    ) -> dict[str, Any]:
        """Process one TradingView event end-to-end (paper path only)."""
        received = received_at or datetime.now(timezone.utc)

        if not self.settings.secret:
            return self._record(
                "NOT_CONFIGURED", None,
                "webhook disabled: QUANTLAB_WEBHOOK_SECRET not set",
                received_at=received,
            )

        if getattr(self.loop.broker, "live_capable", False):
            return self._record(
                "PAPER_GUARD", None,
                "webhook refuses a live-capable broker (paper-only)",
                received_at=received,
            )

        if not self._authenticated(payload, header_secret):
            return self._record(
                "UNAUTHENTICATED", None,
                "missing or invalid webhook secret",
                received_at=received,
            )

        if not isinstance(payload, dict):
            return self._record(
                "MALFORMED", None,
                "payload must be a JSON object",
                received_at=received,
            )

        status, event, reason = self._validate(payload)
        if status is not None:
            return self._record(status, event, reason, received_at=received)

        assert event is not None

        if event.event_id in self._seen_ids:
            return self._record(
                "DUPLICATE", event, "duplicate event_id already processed",
                received_at=received,
            )
        self._seen_ids.add(event.event_id)

        session_status = self.session.check_session(event.event_time).value
        is_24_7 = event.symbol in self.settings.symbols_24_7
        if not is_24_7 and session_status != SessionStatus.OPEN.value:
            return self._record(
                "REJECTED_OUTSIDE_SESSION", event,
                f"session closed ({session_status}) at event time",
                received_at=received, session_status=session_status,
            )

        result = await self._route_to_paper_loop(event, received, bypass_session=is_24_7)
        status = result.get("status")
        body = result.get("result")
        return self._record(
            status, event, result.get("reason", ""),
            received_at=received, session_status=session_status, result=body,
        )

    def _authenticated(self, payload: dict[str, Any] | None, header_secret: str | None) -> bool:
        body_secret = None
        if isinstance(payload, dict):
            candidate = payload.get(SECRET_BODY_FIELD)
            if isinstance(candidate, str):
                body_secret = candidate
        candidates = [s for s in (header_secret, body_secret) if s]
        if not candidates:
            return False
        return secrets.compare_digest(candidates[0], self.settings.secret)

    def _validate(self, payload: dict[str, Any]) -> tuple[str | None, TradingViewEvent | None, str]:
        source = payload.get("source")
        if not isinstance(source, str) or source.strip().lower() not in ALLOWED_SOURCES:
            return "FORBIDDEN_SOURCE", None, "source must be 'tradingview'"

        missing = [
            k for k in ("symbol", "timeframe", "direction", "timestamp") if not payload.get(k)
        ]
        raw_event_id = payload.get("event_id")
        if raw_event_id is not None and not isinstance(raw_event_id, str):
            return "MALFORMED", None, "event_id must be a string when provided"
        if missing:
            return "MALFORMED", None, f"missing required field(s): {', '.join(missing)}"

        raw_ts = payload.get("timestamp")
        try:
            event_time = normalize_timestamp(raw_ts)
        except (ValueError, TypeError, OverflowError) as e:
            return "MALFORMED", None, f"invalid timestamp: {e}"

        now = datetime.now(timezone.utc)
        age = (now - event_time).total_seconds()
        if age > self.settings.max_stale_seconds:
            return "STALE", None, (
                f"event too old ({int(age)}s > {self.settings.max_stale_seconds}s)"
            )
        if age < -self.settings.future_skew_seconds:
            return "FUTURE", None, (
                f"event from the future ({(abs(age)):.0f}s > {self.settings.future_skew_seconds}s)"
            )

        symbol = _normalize_symbol(str(payload.get("symbol")))
        if not SYMBOL_RE.match(symbol):
            return "MALFORMED", None, f"symbol format invalid: {symbol!r}"
        if (
            self.known_symbols
            and symbol not in self.known_symbols
            and symbol not in self.settings.symbols_24_7
        ):
            return "UNKNOWN_SYMBOL", None, f"symbol not in known universe: {symbol}"

        timeframe = str(payload.get("timeframe")).strip().lower()
        if timeframe not in ALLOWED_TIMEFRAMES:
            return "INVALID_TIMEFRAME", None, f"unsupported timeframe: {timeframe!r}"

        raw_direction = str(payload.get("direction")).strip().lower()
        direction = ALLOWED_DIRECTIONS.get(raw_direction)
        if direction is None:
            return "MALFORMED", None, f"invalid direction: {raw_direction!r}"

        price: Decimal | None = None
        raw_price = payload.get("price")
        if raw_price is not None:
            try:
                price = Decimal(str(raw_price))
            except (InvalidOperation, ValueError):
                return "MALFORMED", None, "price must be numeric"
            if price <= 0:
                return "MALFORMED", None, "price must be positive"

        event_id = raw_event_id.strip() if raw_event_id.strip() else _derive_event_id(
            symbol, direction, event_time
        )
        event = TradingViewEvent(
            event_id=event_id,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            event_time=event_time,
            price=price,
            source="tradingview",
            raw=payload,
        )
        return None, event, "ok"

    async def _route_to_paper_loop(
        self, event: TradingViewEvent, received: datetime, *, bypass_session: bool = False
    ) -> dict[str, Any]:
        if event.direction == SignalDirection.NEUTRAL:
            return {"status": "NEUTRAL", "result": None, "reason": "neutral signal (no order)"}

        price = event.price or _cached_price(event.symbol)
        if price is None:
            return {"status": "NO_PRICE", "result": None, "reason": "no price available"}

        bar = _build_bar(event, price)
        signal = Signal(
            strategy_id="tradingview",
            direction=event.direction,
            confidence=self.settings.confidence,
            reason=[
                f"tradingview-webhook:{event.event_id}",
                f"timeframe={event.timeframe}",
            ],
            metadata={
                "source": "tradingview",
                "event_id": event.event_id,
                "symbol": event.symbol,
                "timeframe": event.timeframe,
                "alert_price": str(price),
            },
        )
        try:
            if bypass_session:
                # A 24/7 instrument exempts the NSE session gate, so the loop's
                # own session check must also be satisfied for this execution.
                async with self._bypass_lock:
                    original_session = self.loop.session
                    self.loop.session = _AlwaysOpenSession()
                    try:
                        loop_result = await self.loop.process_signal(signal, bar)
                    finally:
                        self.loop.session = original_session
            else:
                loop_result = await self.loop.process_signal(signal, bar)
        except Exception as e:  # noqa: BLE001
            logger.error("tradingview_loop_error", event=event.event_id, error=str(e))
            return {"status": "FAILED", "result": {"error": str(e)}, "reason": str(e)}

        action = loop_result.get("action")
        if action in ("filled", "partial"):
            status = "FILLED" if action == "filled" else "PARTIAL"
            return {
                "status": status,
                "result": loop_result,
                "reason": f"paper order {'filled' if action == 'filled' else 'partially filled'}",
            }
        if action == "rejected":
            return {
                "status": "REJECTED_BY_RISK",
                "result": loop_result,
                "reason": f"risk rejected: {loop_result.get('reason', '')}",
            }
        if action == "skipped":
            return {
                "status": "SKIPPED",
                "result": loop_result,
                "reason": f"skipped by loop: {loop_result.get('reason', '')}",
            }
        if action == "failed":
            return {
                "status": "FAILED",
                "result": loop_result,
                "reason": f"execution failed: {loop_result.get('error', '')}",
            }
        return {"status": "UNKNOWN", "result": loop_result, "reason": "unhandled loop result"}

    # ------------------------------------------------------------------ queries

    def last_events(self, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            if self._ledger.exists():
                with self._ledger.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if status and rec.get("status") != status:
                            continue
                        events.append(rec)
        except OSError as e:
            logger.error("webhook_ledger_read_failed", path=str(self._ledger), error=str(e))
        return list(reversed(events))[:limit]

    def summary(self) -> dict[str, Any]:
        events = self.last_events(limit=10_000)
        counts: dict[str, int] = {}
        last: dict[str, Any] | None = None
        for rec in events:
            counts[rec.get("status", "UNKNOWN")] = counts.get(rec.get("status", "UNKNOWN"), 0) + 1
            last = last or rec
        return {
            "total_tracked": len(self._seen_ids) if self._loaded_all() else ">=",
            "counts": counts,
            "last_event": last,
            "ledger_path": str(self._ledger),
            "live_capable_broker": getattr(self.loop.broker, "live_capable", False),
        }

    def _loaded_all(self) -> bool:
        return len(self._seen_ids) < _MAX_SEEN_IDS


def _build_bar(event: TradingViewEvent, price: Decimal) -> Bar:
    tick = price * Decimal("0.0005")
    return Bar(
        symbol=event.symbol,
        timestamp=event.event_time,
        open=price,
        high=price + tick,
        low=price - tick,
        close=price,
        volume=1,
    )


def _cached_price(symbol: str) -> Decimal | None:
    try:
        import pickle

        with open("data/genuine_bars.pkl", "rb") as f:
            bars = pickle.load(f)
        series = bars.get(symbol)
        if not series:
            return None
        return Decimal(str(float(series[-1].close)))
    except Exception:  # noqa: BLE001
        return None


def _derive_event_id(symbol: str, direction: SignalDirection, event_time: datetime) -> str:
    """Deterministic id so repeated alert firings within the same minute merge.

    Distinct directions in the same minute stay distinct (exit after entry OK).
    """
    minute_ts = int(event_time.timestamp() // 60)
    return f"tv:{symbol}:{direction.value}:{minute_ts}"


def reason_id(reason: str) -> str:
    digest = hashlib.sha1(reason.encode("utf-8")).hexdigest()[:16]
    return f"noid-{digest}"