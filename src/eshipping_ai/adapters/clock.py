"""Clocks (``Clock``): the system time, or a fixed moment for reproducible runs."""

from datetime import UTC, datetime


class SystemClock:
    """The current time of the machine, in UTC."""

    def now(self) -> datetime:
        """Return the current time."""
        return datetime.now(UTC)


class FixedClock:
    """Always the same moment: replays a past day, as the demo on the synthetic set does."""

    def __init__(self, at: datetime) -> None:
        """Create the clock.

        Args:
            at: The moment it returns; it must carry its time zone.
        """
        if at.tzinfo is None:
            msg = "a fixed clock needs a time zone"
            raise ValueError(msg)
        self._at = at

    def now(self) -> datetime:
        """Return the fixed moment."""
        return self._at
