"""Microsoft Teams / Outlook calendar client — polls via Microsoft Graph API.

Uses MSAL with device-code flow for authentication. Works with any calendar
visible in Teams/Outlook, including on Windows native and iOS.
Events synced from any device (Windows, iOS, Android, web) are accessible.
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone

import msal
import httpx

from config import MS_CLIENT_ID, MS_TENANT_ID, MS_CALENDAR_ID

logger = logging.getLogger("sbb-not")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.Read"]
TOKEN_CACHE_FILE = "ms_token_cache.json"

AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"


def _build_msal_app() -> msal.PublicClientApplication:
    """Build an MSAL public client with persistent token cache."""
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        MS_CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )
    return app


def _save_cache(app: msal.PublicClientApplication) -> None:
    """Persist the MSAL token cache to disk."""
    if app.token_cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(app.token_cache.serialize())


def _get_access_token() -> str:
    """Acquire a Graph API access token, using cache or device-code flow."""
    if not MS_CLIENT_ID:
        raise ValueError(
            "MS_CLIENT_ID is not set. Register an app in Azure Entra ID "
            "(Azure Portal → App registrations) and set MS_CLIENT_ID in .env"
        )

    app = _build_msal_app()

    # Try silent token acquisition first (cached/refresh token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(app)
            return result["access_token"]

    # Fall back to device-code flow (works headlessly, on any OS)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device code flow failed: {flow.get('error_description', 'unknown error')}")

    print(f"\n{'=' * 60}")
    print(f"Microsoft sign-in required.")
    print(f"1. Open: {flow['verification_uri']}")
    print(f"2. Enter code: {flow['user_code']}")
    print(f"{'=' * 60}\n")
    logger.info(f"Waiting for Microsoft authentication (code: {flow['user_code']})...")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown"))
        raise RuntimeError(f"Microsoft authentication failed: {error}")

    _save_cache(app)
    logger.info("✅ Microsoft authentication successful")
    return result["access_token"]


def get_graph_headers() -> dict[str, str]:
    """Get authorization headers for Graph API calls."""
    token = _get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def fetch_upcoming_events(hours_ahead: int = 6) -> list[dict]:
    """Fetch calendar events from Microsoft Graph in the next N hours.

    Returns events in a format compatible with the Google Calendar structure
    so the same parser can process them.
    """
    headers = get_graph_headers()
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT%H:%M:%S.0000000")
    time_max = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%dT%H:%M:%S.0000000")

    # Use calendarView for expanded recurring events
    if MS_CALENDAR_ID:
        url = f"{GRAPH_BASE}/me/calendars/{MS_CALENDAR_ID}/calendarView"
    else:
        url = f"{GRAPH_BASE}/me/calendarView"

    params = {
        "startDateTime": time_min,
        "endDateTime": time_max,
        "$orderby": "start/dateTime",
        "$top": "20",
        "$select": "id,subject,bodyPreview,body,start,end,location,categories",
    }

    with httpx.Client() as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    # Convert Microsoft Graph events to Google Calendar-like format
    # so sbb_parser can process them identically
    events = []
    for item in data.get("value", []):
        event = _convert_to_gcal_format(item)
        events.append(event)

    return events


def _convert_to_gcal_format(ms_event: dict) -> dict:
    """Convert a Microsoft Graph event to Google Calendar event format.

    This lets the existing sbb_parser work unchanged for both backends.
    """
    start = ms_event.get("start", {})
    end = ms_event.get("end", {})

    # Graph returns dateTime + timeZone separately
    start_dt = start.get("dateTime", "")
    start_tz = start.get("timeZone", "UTC")
    end_dt = end.get("dateTime", "")
    end_tz = end.get("timeZone", "UTC")

    # Convert to ISO format with timezone offset for consistency
    start_iso = _graph_datetime_to_iso(start_dt, start_tz)
    end_iso = _graph_datetime_to_iso(end_dt, end_tz)

    location = ms_event.get("location", {})
    location_str = location.get("displayName", "") if isinstance(location, dict) else str(location)

    # Use bodyPreview for description (plain text), fall back to body content
    description = ms_event.get("bodyPreview", "")
    if not description:
        body = ms_event.get("body", {})
        description = body.get("content", "") if isinstance(body, dict) else ""

    return {
        "id": ms_event.get("id", ""),
        "summary": ms_event.get("subject", ""),
        "description": description,
        "location": location_str,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }


def _graph_datetime_to_iso(dt_str: str, tz_name: str) -> str:
    """Convert Graph API datetime + timezone to ISO 8601 string.

    Graph returns e.g. "2026-04-18T08:30:00.0000000" with a separate timeZone field.
    We need "2026-04-18T08:30:00+02:00" for fromisoformat().
    """
    if not dt_str:
        return ""

    # Strip trailing zeros from fractional seconds
    dt_str = dt_str.rstrip("0").rstrip(".")

    try:
        from zoneinfo import ZoneInfo
        naive = datetime.fromisoformat(dt_str)
        tz = ZoneInfo(tz_name) if tz_name and tz_name != "UTC" else timezone.utc
        aware = naive.replace(tzinfo=tz)
        return aware.isoformat()
    except Exception:
        # Fallback: assume UTC
        if not dt_str.endswith("Z") and "+" not in dt_str and "-" not in dt_str[10:]:
            dt_str += "Z"
        return dt_str
