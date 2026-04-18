"""Google Calendar client — polls for SBB journey events."""

import os
import pickle
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import GOOGLE_CALENDAR_ID, GOOGLE_CREDENTIALS_FILE

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = "token.pickle"
REDIRECT_URI = "http://localhost"


def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {GOOGLE_CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console → APIs → Credentials → OAuth 2.0 Client ID"
                )
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
            flow = Flow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
            )
            auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
            print(f"\n1. Open this URL in your browser:\n\n   {auth_url}\n")
            print("2. Authorize the app. The browser will redirect to a page that won't load.")
            print("3. Copy the FULL URL from your browser's address bar and paste it here.\n")
            redirect_response = input("Paste the redirect URL: ").strip()
            flow.fetch_token(authorization_response=redirect_response)
            creds = flow.credentials
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return creds


def get_calendar_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def fetch_upcoming_events(service, hours_ahead: int = 6) -> list[dict]:
    """Fetch calendar events happening in the next N hours."""
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(hours=hours_ahead)).isoformat()

    result = (
        service.events()
        .list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        )
        .execute()
    )
    return result.get("items", [])
