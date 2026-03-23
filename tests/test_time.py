"""Tests for vigil_time — monotonic timer and day tracking."""

import time
from datetime import date, datetime, timezone

import pytest

from vigil_time import MonotonicTimer, DayTracker, utc_now_iso, today_iso


class TestMonotonicTimer:
    def test_tick_returns_positive(self):
        timer = MonotonicTimer()
        time.sleep(0.01)
        dt = timer.tick()
        assert dt > 0

    def test_tick_resets(self):
        timer = MonotonicTimer()
        time.sleep(0.01)
        dt1 = timer.tick()
        dt2 = timer.tick()
        assert dt2 < dt1  # Second tick should be much shorter

    def test_peek_does_not_reset(self):
        timer = MonotonicTimer()
        time.sleep(0.01)
        p1 = timer.peek()
        p2 = timer.peek()
        assert p2 >= p1

    def test_reset(self):
        timer = MonotonicTimer()
        time.sleep(0.01)
        timer.reset()
        dt = timer.tick()
        assert dt < 0.1  # Should be very small after reset


class TestDayTracker:
    def test_no_change_same_day(self):
        tracker = DayTracker()
        assert tracker.check_day_change() is None

    def test_detect_gap(self):
        tracker = DayTracker()
        # Yesterday's timestamp
        yesterday = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) -
                     __import__('datetime').timedelta(days=1))
        result = tracker.detect_gap(yesterday.isoformat())
        assert result is not None
        assert result < date.today()

    def test_no_gap_today(self):
        tracker = DayTracker()
        result = tracker.detect_gap(datetime.now(timezone.utc).isoformat())
        assert result is None

    def test_no_gap_empty_string(self):
        tracker = DayTracker()
        assert tracker.detect_gap("") is None

    def test_no_gap_invalid(self):
        tracker = DayTracker()
        assert tracker.detect_gap("not-a-date") is None


class TestDayTrackerProperties:
    def test_current_date_property(self):
        tracker = DayTracker()
        assert tracker.current_date == date.today()

    def test_day_change_returns_previous_date(self):
        tracker = DayTracker()
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        tracker._current_date = yesterday

        previous = tracker.check_day_change()
        assert previous == yesterday
        assert tracker.current_date == date.today()

    def test_day_change_updates_current(self):
        tracker = DayTracker()
        from datetime import timedelta
        tracker._current_date = date.today() - timedelta(days=1)
        tracker.check_day_change()
        # After detecting change, current should be today
        assert tracker.current_date == date.today()
        # Second call should return None (no change)
        assert tracker.check_day_change() is None


class TestHelpers:
    def test_utc_now_iso(self):
        result = utc_now_iso()
        assert "T" in result
        assert "+" in result or "Z" in result

    def test_today_iso(self):
        result = today_iso()
        assert len(result) == 10  # YYYY-MM-DD
        assert result.count("-") == 2
