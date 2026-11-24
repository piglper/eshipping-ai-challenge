from datetime import UTC, datetime

import pytest

from eshipping_ai.adapters.clock import FixedClock, SystemClock


def test_the_system_clock_is_aware() -> None:
    assert SystemClock().now().tzinfo is UTC


def test_a_fixed_clock_needs_a_time_zone() -> None:
    moment = datetime(2026, 10, 7, 8, tzinfo=UTC)
    assert FixedClock(moment).now() == moment
    with pytest.raises(ValueError, match="time zone"):
        FixedClock(datetime(2026, 10, 7, 8))  # noqa: DTZ001 - the case under test
