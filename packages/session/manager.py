"""Session Manager — market hours, calendar, and trading session detection.

All session decisions are evaluated in the exchange's local timezone
(Asia/Kolkata for NSE). Input datetimes that are timezone-naive are treated
as UTC and converted; timezone-aware datetimes are converted to the calendar
timezone before comparison.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from packages.core.logging import get_logger

logger = get_logger("session_manager")

IST_FALLBACK = timezone(timedelta(hours=5, minutes=30))

_SESSION_TZ_CACHE: dict[str, ZoneInfo | timezone] = {}


def _session_tz(tz_name: str) -> ZoneInfo | timezone:
    cached = _SESSION_TZ_CACHE.get(tz_name)
    if cached is not None:
        return cached
    try:
        tz: ZoneInfo | timezone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("session_timezone_fallback", requested=tz_name, fallback="UTC+05:30")
        tz = IST_FALLBACK
    _SESSION_TZ_CACHE[tz_name] = tz
    return tz


class SessionStatus(str, Enum):
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTERNOON = "afternoon"
    CLOSED = "closed"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    UNKNOWN = "unknown"


@dataclass
class MarketCalendar:
    name: str = "NSE"
    timezone_name: str = "Asia/Kolkata"
    open_time: time = time(9, 15)
    close_time: time = time(15, 30)
    pre_market_minutes: int = 15
    holidays: set[date] = field(default_factory=set)

    def is_weekend(self, dt: date) -> bool:
        return dt.weekday() >= 5

    def is_holiday(self, dt: date) -> bool:
        return dt in self.holidays

    @property
    def tz(self) -> ZoneInfo | timezone:
        return _session_tz(self.timezone_name)

    def pre_market_start(self) -> time:
        start = (
            datetime.combine(date.min, self.open_time) - timedelta(minutes=self.pre_market_minutes)
        ).time()
        return start


class SessionManager:
    def __init__(self, calendar: MarketCalendar | None = None):
        self.calendar = calendar or MarketCalendar()
        self._status = SessionStatus.UNKNOWN
        self._last_check: datetime | None = None

    def _to_local(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(self.calendar.tz)

    def check_session(self, dt: datetime | None = None) -> SessionStatus:
        now = dt or datetime.now(timezone.utc)
        self._last_check = now
        local = self._to_local(now)
        local_date = local.date()

        if self.calendar.is_weekend(local_date):
            self._status = SessionStatus.WEEKEND
            return self._status

        if self.calendar.is_holiday(local_date):
            self._status = SessionStatus.HOLIDAY
            return self._status

        local_time = local.time()
        open_t = self.calendar.open_time
        close_t = self.calendar.close_time
        pre_market_start = self.calendar.pre_market_start()

        if local_time < pre_market_start:
            self._status = SessionStatus.CLOSED
        elif local_time < open_t:
            self._status = SessionStatus.PRE_MARKET
        elif local_time <= close_t:
            self._status = SessionStatus.OPEN
        else:
            self._status = SessionStatus.CLOSED

        return self._status

    def is_open(self, dt: datetime | None = None) -> bool:
        return self.check_session(dt) == SessionStatus.OPEN

    def is_pre_market(self, dt: datetime | None = None) -> bool:
        return self.check_session(dt) == SessionStatus.PRE_MARKET

    def _ensure_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def time_to_close(self, dt: datetime | None = None) -> timedelta:
        now = self._to_local(self._ensure_utc(dt or datetime.now(timezone.utc)))
        close = datetime.combine(
            now.date(), self.calendar.close_time, tzinfo=self.calendar.tz
        )
        if now >= close:
            close += timedelta(days=1)
        return close - now

    def time_to_open(self, dt: datetime | None = None) -> timedelta:
        now = self._to_local(self._ensure_utc(dt or datetime.now(timezone.utc)))
        open_dt = datetime.combine(now.date(), self.calendar.open_time, tzinfo=self.calendar.tz)
        if now >= open_dt:
            open_dt = self._next_trading_day(open_dt)
        return open_dt - now

    def next_session_start(self, dt: datetime | None = None) -> datetime:
        now = self._to_local(self._ensure_utc(dt or datetime.now(timezone.utc)))
        candidate = datetime.combine(
            now.date(), self.calendar.open_time, tzinfo=self.calendar.tz
        )
        if now >= candidate:
            candidate += timedelta(days=1)
        while self.calendar.is_weekend(candidate.date()) or self.calendar.is_holiday(
            candidate.date()
        ):
            candidate += timedelta(days=1)
        return candidate

    def _next_trading_day(self, candidate: datetime) -> datetime:
        candidate += timedelta(days=1)
        while self.calendar.is_weekend(candidate.date()) or self.calendar.is_holiday(
            candidate.date()
        ):
            candidate += timedelta(days=1)
        return candidate

    def status(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "status": self._status.value if self._status else SessionStatus.UNKNOWN.value,
            "session": self.check_session(now).value,
            "is_open": self._status == SessionStatus.OPEN,
            "calendar": self.calendar.name,
            "timezone": self.calendar.timezone_name,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "time_to_close_sec": self.time_to_close(now).total_seconds(),
            "time_to_open_sec": self.time_to_open(now).total_seconds(),
            "next_open": self.next_session_start(now).isoformat(),
        }