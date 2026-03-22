"""
Vigil Time — Monotonic time tracking immune to NTP jumps and missing RTC.

Uses time.monotonic() for all duration calculations.
Wall clock (datetime.now) only for timestamps in saved data and day-change detection.
"""

import time
from datetime import datetime, date, timezone


class MonotonicTimer:
    """Tracks elapsed time using monotonic clock."""

    def __init__(self):
        self._last_tick = time.monotonic()

    def tick(self) -> float:
        """Return seconds elapsed since last tick, then reset."""
        now = time.monotonic()
        delta = now - self._last_tick
        self._last_tick = now
        # Guard against negative deltas (shouldn't happen with monotonic, but be safe)
        return max(0.0, delta)

    def peek(self) -> float:
        """Return seconds since last tick WITHOUT resetting."""
        return max(0.0, time.monotonic() - self._last_tick)

    def reset(self):
        """Reset the timer to now."""
        self._last_tick = time.monotonic()


class DayTracker:
    """Detects day changes using wall clock."""

    def __init__(self):
        self._current_date = date.today()

    @property
    def current_date(self) -> date:
        return self._current_date

    def check_day_change(self) -> date | None:
        """
        Check if the day has changed.
        Returns the previous date if day changed, None otherwise.
        """
        today = date.today()
        if today != self._current_date:
            previous = self._current_date
            self._current_date = today
            return previous
        return None

    def detect_gap(self, last_saved_iso: str) -> date | None:
        """
        Detect if there's a date gap from last_saved to now.
        Used at startup to close out the previous day's snapshot.
        Returns the last active date if there's a gap, None otherwise.
        """
        if not last_saved_iso:
            return None
        try:
            last_dt = datetime.fromisoformat(last_saved_iso)
            last_date = last_dt.date()
        except (ValueError, TypeError):
            return None

        today = date.today()
        if last_date < today:
            return last_date
        return None


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    """Return today's date as ISO 8601 string (YYYY-MM-DD)."""
    return date.today().isoformat()
