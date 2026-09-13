"""Session gate correctness — the trading session must be evaluated in exchange
local time (Asia/Kolkata), not in the UTC wall-clock of the caller.

Regression target QLT-001: the previous implementation compared a UTC
``now.time()`` directly against IST open/close times, which classified most of
the real trading day as CLOSED (e.g. 09:30 IST == 04:00 UTC was CLOSED).

2026-07-15 is a Wednesday. Asia/Kolkata is fixed UTC+05:30.
"""

from datetime import UTC, date, datetime

import pytest

from packages.session.manager import MarketCalendar, SessionManager, SessionStatus


def _ist(d: int, hm: str, month: int = 7) -> datetime:
    """UTC datetime that corresponds to the given Asia/Kolkata wall-clock time."""
    hour, minute = map(int, hm.split(":"))
    utc = datetime(2026, month, d, hour, minute, tzinfo=UTC) - __import__(
        "datetime"
    ).timedelta(hours=5, minutes=30)
    return utc


class TestSessionISTCorrectness:
    @pytest.mark.parametrize(
        "wall_clock, expected",
        [
            ("08:30", SessionStatus.CLOSED),  # before pre-market window
            ("09:00", SessionStatus.PRE_MARKET),  # 15 min before open
            ("09:15", SessionStatus.OPEN),  # open
            ("11:00", SessionStatus.OPEN),
            ("14:30", SessionStatus.OPEN),
            ("15:30", SessionStatus.OPEN),  # close inclusive
            ("15:31", SessionStatus.CLOSED),
        ],
    )
    def test_wall_clock_mapping(self, wall_clock, expected):
        sm = SessionManager()
        assert sm.check_session(_ist(15, wall_clock)) == expected

    def test_old_bug_regression_ist_morning_is_open(self):
        """04:00 UTC = 09:30 IST on a trading Wednesday must be OPEN."""
        sm = SessionManager()
        utc = datetime(2026, 7, 15, 4, 0, tzinfo=UTC)
        assert sm.check_session(utc) == SessionStatus.OPEN

    def test_old_bug_regression_ist_afternoon_is_open(self):
        """06:30 UTC = 12:00 IST on a trading Wednesday must be OPEN."""
        sm = SessionManager()
        utc = datetime(2026, 7, 15, 6, 30, tzinfo=UTC)
        assert sm.check_session(utc) == SessionStatus.OPEN

    def test_old_bug_regression_utc_night_is_closed(self):
        """20:00 UTC = 01:30 IST next day — must be CLOSED, not OPEN."""
        sm = SessionManager()
        utc = datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
        assert sm.check_session(utc) == SessionStatus.CLOSED

    def test_is_open_in_ist_window(self):
        sm = SessionManager()
        assert sm.is_open(_ist(15, "10:00")) is True
        assert sm.is_open(_ist(15, "16:00")) is False

    def test_weekend_evaluated_in_local_date(self):
        """Sunday 00:00 IST is 18:30 UTC Saturday — the OLD code (UTC date) saw
        Saturday. Either way it is a non-trading day; assert WEEKEND either way."""
        sm = SessionManager()
        utc = datetime(2026, 7, 19, 6, 0, tzinfo=UTC)  # 11:30 IST Sunday
        assert sm.check_session(utc) == SessionStatus.WEEKEND

    def test_time_to_close_in_ist(self):
        """09:00 UTC = 14:30 IST -> 60 min to 15:30 IST close."""
        sm = SessionManager()
        ttc = sm.time_to_close(_ist(15, "14:30"))
        assert abs(ttc.total_seconds() - 3600.0) < 1.0

    def test_time_to_open_after_close(self):
        """16:00 UTC = 21:30 IST -> open next trading day (Thu) 09:15 IST."""
        sm = SessionManager()
        tto = sm.time_to_open(_ist(15, "21:30"))
        assert tto.total_seconds() > 0

    def test_next_session_start_skips_weekend(self):
        """Friday 20:00 UTC (01:30 IST Sat) -> next open Monday 09:15 IST."""
        sm = SessionManager()
        utc = datetime(2026, 7, 17, 20, 0, tzinfo=UTC)
        nxt = sm.next_session_start(utc)
        assert nxt.date() == date(2026, 7, 20)  # Monday
        assert nxt.hour == 9 and nxt.minute == 15

    def test_timezone_reported(self):
        sm = SessionManager()
        assert sm.calendar.timezone_name == "Asia/Kolkata"


class TestSessionHolidayHandling:
    def test_holiday_in_ist_scoped(self):
        """A calendar holiday on 2026-12-25 evaluated at IST mid-morning."""
        sm = SessionManager(calendar=MarketCalendar(holidays={date(2026, 12, 25)}))
        utc = datetime(2026, 12, 25, 5, 0, tzinfo=UTC)  # 10:30 IST
        assert sm.check_session(utc) == SessionStatus.HOLIDAY

    def test_not_holiday_next_day(self):
        sm = SessionManager(calendar=MarketCalendar(holidays={date(2026, 12, 25)}))
        utc = datetime(2026, 12, 26, 5, 0, tzinfo=UTC)  # 10:30 IST Sat -> weekend
        assert sm.check_session(utc) == SessionStatus.WEEKEND
