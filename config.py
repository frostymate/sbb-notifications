import os
from dotenv import load_dotenv

load_dotenv()

POLL_IDLE = int(os.getenv("POLL_IDLE", "300"))
POLL_APPROACHING = int(os.getenv("POLL_APPROACHING", "120"))
POLL_ACTIVE = int(os.getenv("POLL_ACTIVE", "30"))

NOTIFY_MINUTES_BEFORE = int(os.getenv("NOTIFY_MINUTES_BEFORE", "2"))

# Calendar backend: "google" or "teams"
CALENDAR_BACKEND = os.getenv("CALENDAR_BACKEND", "google")

# Google Calendar settings
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Microsoft Teams / Outlook Calendar settings (via Microsoft Graph API)
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "common")
MS_CALENDAR_ID = os.getenv("MS_CALENDAR_ID", "")  # empty = default calendar

NOTIFICATION_BACKEND = os.getenv("NOTIFICATION_BACKEND", "native")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Zurich")
