"""Session Manager — market hours, calendar, and trading session detection."""

from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from enum import Enum

from packages.core.logging import get_logger

logger = get_logger("session_manager")


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
    lunch_start: time | None = time(12, 0)
    lunch_end: time | None = time(12, 45)
    holidays: set[date] = field(default_factory=set)

    def is_weekend(self, dt: date) -> bool:
        return dt.weekday() >= 5

    def is_holiday(self, dt: date) -> bool:
        return dt in self.holidays


class SessionManager:
    def __init__(self, calendar: MarketCalendar | None = None):
        self.calendar = calendar or MarketCalendar()
        self._status = SessionStatus.UNKNOWN
        self._last_check: datetime | None = None

    def check_session(self, dt: datetime | None = None) -> SessionStatus:
        now = dt or datetime.now(timezone.utc)
        self._last_check = now

        if self.calendar.is_weekend(now.date()):
            self._status = SessionStatus.WEEKEND
            return self._status

        if self.calendar.is_holiday(now.date()):
            self._status = SessionStatus.HOLIDAY
            return self._status

        local_time = now.time()
        open_t = self.calendar.open_time
        close_t = self.calendar.close_time

        pre_market_end = time(open_t.hour, max(0, open_t.minute - 15))

        if local_time < pre_market_end:
            self._status = SessionStatus.CLOSED
        elif local_time < open_t:
            self._status = SessionStatus.PRE_MARKET
        elif local_time <= close_t:
            if self.calendar.lunch_start and self.calendar.lunch_end:
                if self.calendar.lunch_start <= local_time < self.calendar.lunch_end:
                    self._status = SessionStatus.OPEN
                else:
                    self._status = SessionStatus.OPEN
            else:
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
        now = self._ensure_utc(dt or datetime.now(timezone.utc))
        close = datetime.combine(now.date(), self.calendar.close_time, tzinfo=timezone.utc)
        if now.time() > self.calendar.close_time:
            close += timedelta(days=1)
        return close - now

    def time_to_open(self, dt: datetime | None = None) -> timedelta:
        now = self._ensure_utc(dt or datetime.now(timezone.utc))
        open_dt = datetime.combine(now.date(), self.calendar.open_time, tzinfo=timezone.utc)
        if now.time() > self.calendar.open_time:
            open_dt += timedelta(days=1)
            while self.calendar.is_weekend(open_dt.date()) or self.calendar.is_holiday(
                open_dt.date()
            ):
                open_dt += timedelta(days=1)
        return open_dt - now

    def next_session_start(self, dt: datetime | None = None) -> datetime:
        now = self._ensure_utc(dt or datetime.now(timezone.utc))
        candidate = datetime.combine(now.date(), self.calendar.open_time, tzinfo=timezone.utc)
        if now >= candidate:
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
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "time_to_close_sec": self.time_to_close(now).total_seconds(),
            "time_to_open_sec": self.time_to_open(now).total_seconds(),
            "next_open": self.next_session_start(now).isoformat(),
        }
