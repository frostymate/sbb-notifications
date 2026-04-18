"""Parse SBB calendar events into structured journey data.

SBB "Add to Calendar" events typically look like:
  Title: "Zürich HB - Bern"  or  "IC 1 708 Zürich HB - Bern"
  Description: Contains departure/arrival times, platform, train number,
               intermediate stops, and transfer info.
  Start/End: Departure and arrival times of the full journey.

We parse these into Journey objects with legs and stops.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Stop:
    name: str
    arrival: datetime | None = None
    departure: datetime | None = None
    platform: str | None = None
    delay: int | None = None  # delay in minutes from API
    prognosis_arrival: datetime | None = None
    prognosis_departure: datetime | None = None
    prognosis_platform: str | None = None


@dataclass
class Leg:
    """One segment of a journey (one train/bus/tram)."""
    from_station: str
    to_station: str
    departure: datetime
    arrival: datetime
    train_type: str | None = None  # IC, IR, RE, S, Bus, Tram
    train_number: str | None = None
    intermediate_stops: list[Stop] = field(default_factory=list)
    departure_platform: str | None = None
    arrival_platform: str | None = None
    departure_delay: int | None = None  # minutes
    arrival_delay: int | None = None  # minutes


@dataclass
class Journey:
    """A full journey, possibly with multiple legs (transfers)."""
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    legs: list[Leg] = field(default_factory=list)
    event_id: str = ""
    raw_title: str = ""
    raw_description: str = ""


# Common Swiss train types
TRAIN_TYPES = r"(?:IC|IR|RE|RB|S|EC|EN|TGV|ICE|Bus|Tram|NFB|NFT)"

# Station name pattern (allows umlauts, spaces, abbreviations)
STATION_PATTERN = r"[A-ZÀ-Ža-zà-ž0-9\s\.\-\']+"


def parse_title(title: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract origin, destination, train type, and number from event title.

    Examples:
        "Zürich HB - Bern" → ("Zürich HB", "Bern", None, None)
        "IC 708 Zürich HB - Bern" → ("Zürich HB", "Bern", "IC", "708")
        "S8 Zürich HB - Winterthur" → ("Zürich HB", "Winterthur", "S", "8")
    """
    # Try: "[TrainType] [Number] Origin - Destination"
    m = re.match(
        rf"^({TRAIN_TYPES})\s*(\d+)?\s*(.+?)\s*[-–—→]\s*(.+)$",
        title.strip(),
        re.IGNORECASE,
    )
    if m:
        return m.group(3).strip(), m.group(4).strip(), m.group(1), m.group(2)

    # Try: "Origin - Destination" (no train info)
    m = re.match(r"^(.+?)\s*[-–—→]\s*(.+)$", title.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip(), None, None

    return None, None, None, None


def is_sbb_event(event: dict) -> bool:
    """Heuristic: is this calendar event an SBB journey?"""
    title = event.get("summary", "").lower()
    description = (event.get("description") or "").lower()
    location = (event.get("location") or "").lower()

    # Check for Swiss transport indicators
    sbb_keywords = [
        "sbb", "cff", "ffs",  # SBB in three languages
        "gleis", "perron", "voie", "platform",  # platform references
        "zürich", "zurich", "bern", "basel", "luzern", "lucerne",
        "winterthur", "st. gallen", "lausanne", "genève",
    ]
    train_patterns = [r"\b(IC|IR|RE|S\d|EC|EN)\b"]

    text = f"{title} {description} {location}"

    for kw in sbb_keywords:
        if kw in text:
            return True
    for pat in train_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True

    # Check if title has "Station - Station" pattern
    origin, dest, _, _ = parse_title(event.get("summary", ""))
    if origin and dest:
        # Could be a journey — we'll verify with transport API later
        return True

    return False


def parse_event_times(event: dict) -> tuple[datetime | None, datetime | None]:
    """Extract start and end times from a Google Calendar event."""
    start_raw = event.get("start", {}).get("dateTime")
    end_raw = event.get("end", {}).get("dateTime")

    start = datetime.fromisoformat(start_raw) if start_raw else None
    end = datetime.fromisoformat(end_raw) if end_raw else None
    return start, end


def parse_event(event: dict) -> Journey | None:
    """Parse a Google Calendar event into a Journey, or None if not SBB."""
    if not is_sbb_event(event):
        return None

    title = event.get("summary", "")
    description = event.get("description", "") or ""
    start, end = parse_event_times(event)

    if not start or not end:
        return None

    origin, destination, train_type, train_number = parse_title(title)
    if not origin or not destination:
        return None

    leg = Leg(
        from_station=origin,
        to_station=destination,
        departure=start,
        arrival=end,
        train_type=train_type,
        train_number=train_number,
    )

    journey = Journey(
        origin=origin,
        destination=destination,
        departure=start,
        arrival=end,
        legs=[leg],
        event_id=event.get("id", ""),
        raw_title=title,
        raw_description=description,
    )

    return journey
