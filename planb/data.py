"""Loading static fixtures and the World (places + travel-time matrix)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .models import Booking, Place, TravelTime, Trip

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class World:
    """Read-only static knowledge: places and travel times. Missing data stays unknown."""

    def __init__(self, places: list[Place], travel: list[TravelTime], timezone: str = "Asia/Tokyo"):
        self.places = {p.place_id: p for p in places}
        self.tz = ZoneInfo(timezone)
        self._travel: dict[tuple[str, str], TravelTime] = {}
        for tt in travel:
            self._travel[(tt.origin_place_id, tt.destination_place_id)] = tt
            self._travel.setdefault(
                (tt.destination_place_id, tt.origin_place_id),
                tt.model_copy(update={"origin_place_id": tt.destination_place_id,
                                      "destination_place_id": tt.origin_place_id}),
            )

    def place(self, place_id: str) -> Optional[Place]:
        return self.places.get(place_id)

    def travel(self, origin: str, destination: str) -> Optional[TravelTime]:
        """Return the travel record or None if UNKNOWN (never assume 0 minutes)."""
        if origin == destination:
            return TravelTime(origin_place_id=origin, destination_place_id=destination,
                              mode="same_place", travel_minutes=0, travel_cost_minor=0)
        return self._travel.get((origin, destination))

    def travel_minutes(self, origin: str, destination: str) -> Optional[int]:
        tt = self.travel(origin, destination)
        return tt.travel_minutes if tt else None

    def local(self, dt: datetime) -> datetime:
        return dt.astimezone(self.tz)


def load_world(places_file: Path | None = None, matrix_file: Path | None = None) -> World:
    places_file = places_file or DATA / "places/tokyo_places.json"
    matrix_file = matrix_file or DATA / "travel_times/tokyo_matrix.json"
    places = [Place.model_validate(p) for p in json.loads(Path(places_file).read_text())]
    travel = [TravelTime.model_validate(t) for t in json.loads(Path(matrix_file).read_text())]
    return World(places, travel)


def load_trip(path: Path | None = None) -> Trip:
    path = path or DATA / "sample_trips/tokyo_3day.json"
    return Trip.model_validate(json.loads(Path(path).read_text()))


def load_bookings(path: Path | None = None) -> list[Booking]:
    path = path or DATA / "sample_bookings/tokyo_bookings.json"
    return [Booking.model_validate(b) for b in json.loads(Path(path).read_text())]
