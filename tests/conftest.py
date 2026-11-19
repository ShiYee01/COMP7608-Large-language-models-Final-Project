import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planb.data import load_bookings, load_trip, load_world  # noqa: E402


@pytest.fixture
def world():
    return load_world()


@pytest.fixture
def trip():
    return load_trip()


@pytest.fixture
def bookings():
    return load_bookings()


def jst(s: str) -> datetime:
    return datetime.fromisoformat(s + "+09:00")
