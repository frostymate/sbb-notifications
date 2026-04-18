"""Client for transport.opendata.ch — free Swiss public transport API."""

import httpx
from datetime import datetime
from urllib.parse import quote

from sbb_parser import Leg, Stop

API_BASE = "https://transport.opendata.ch/v1"

SBB_TIMETABLE_URL = "https://www.sbb.ch/en/timetable.html"


def build_sbb_url(from_station: str, to_station: str, departure: datetime) -> str:
    """Build an SBB timetable URL for a journey."""
    params = (
        f"from={quote(from_station)}"
        f"&to={quote(to_station)}"
        f"&date={departure.strftime('%Y-%m-%d')}"
        f"&time={departure.strftime('%H:%M')}"
    )
    return f"{SBB_TIMETABLE_URL}?{params}"


async def resolve_station(name: str) -> dict | None:
    """Resolve a station name to its canonical form + coordinates."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/locations", params={"query": name, "type": "station"})
        resp.raise_for_status()
        stations = resp.json().get("stations", [])
        return stations[0] if stations else None


async def fetch_connection(
    from_station: str,
    to_station: str,
    departure_time: datetime,
) -> list[dict] | None:
    """Fetch connections from the transport API.

    Returns the raw connection data including all stops per leg.
    """
    params = {
        "from": from_station,
        "to": to_station,
        "date": departure_time.strftime("%Y-%m-%d"),
        "time": departure_time.strftime("%H:%M"),
        "limit": 4,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/connections", params=params)
        resp.raise_for_status()
        return resp.json().get("connections", [])


def find_best_connection(connections: list[dict], target_departure: datetime) -> dict | None:
    """Find the connection closest to our expected departure time."""
    best = None
    best_diff = float("inf")

    for conn in connections:
        dep_str = conn.get("from", {}).get("departure")
        if not dep_str:
            continue
        dep = datetime.fromisoformat(dep_str)
        diff = abs((dep - target_departure).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best = conn

    return best


def connection_to_legs(connection: dict) -> list[Leg]:
    """Convert a transport API connection into our Leg objects with all intermediate stops."""
    legs = []

    for section in connection.get("sections", []):
        journey_data = section.get("journey")
        dep = section.get("departure", {})
        arr = section.get("arrival", {})

        from_station = dep.get("station", {}).get("name", "?")
        to_station = arr.get("station", {}).get("name", "?")

        dep_time_str = dep.get("departure")
        arr_time_str = arr.get("arrival")

        if not dep_time_str or not arr_time_str:
            continue

        dep_time = datetime.fromisoformat(dep_time_str)
        arr_time = datetime.fromisoformat(arr_time_str)

        # Platform info
        dep_platform = dep.get("platform")
        arr_platform = arr.get("platform")

        # Delay / prognosis
        dep_prognosis = dep.get("prognosis") or {}
        arr_prognosis = arr.get("prognosis") or {}
        dep_delay = dep.get("delay")  # minutes, from API
        arr_delay = arr.get("delay")

        # Use prognosis platform if available (real-time platform change)
        if dep_prognosis.get("platform"):
            dep_platform = dep_prognosis["platform"]
        if arr_prognosis.get("platform"):
            arr_platform = arr_prognosis["platform"]

        # Train info
        train_type = None
        train_number = None
        if journey_data:
            cat = journey_data.get("category", "")
            num = journey_data.get("number", "")
            train_type = cat if cat else None
            train_number = num if num else None

        # Intermediate stops
        stops = []
        if journey_data:
            pass_list = journey_data.get("passList", [])
            for p in pass_list:
                p_prognosis = p.get("prognosis") or {}
                stop = Stop(
                    name=p.get("station", {}).get("name", "?"),
                    arrival=datetime.fromisoformat(p["arrival"]) if p.get("arrival") else None,
                    departure=datetime.fromisoformat(p["departure"]) if p.get("departure") else None,
                    platform=p_prognosis.get("platform") or p.get("platform"),
                    delay=p.get("delay"),
                    prognosis_arrival=datetime.fromisoformat(p_prognosis["arrival"]) if p_prognosis.get("arrival") else None,
                    prognosis_departure=datetime.fromisoformat(p_prognosis["departure"]) if p_prognosis.get("departure") else None,
                    prognosis_platform=p_prognosis.get("platform"),
                )
                stops.append(stop)

        # Walking sections (transfers)
        if section.get("walk"):
            legs.append(Leg(
                from_station=from_station,
                to_station=to_station,
                departure=dep_time,
                arrival=arr_time,
                train_type="Walk",
                train_number=None,
                intermediate_stops=[],
            ))
        else:
            legs.append(Leg(
                from_station=from_station,
                to_station=to_station,
                departure=dep_time,
                arrival=arr_time,
                train_type=train_type,
                train_number=train_number,
                intermediate_stops=stops,
                departure_platform=dep_platform,
                arrival_platform=arr_platform,
                departure_delay=dep_delay,
                arrival_delay=arr_delay,
            ))

    return legs
