import os
from dotenv import load_dotenv

load_dotenv()

POLL_IDLE = int(os.getenv("POLL_IDLE", "300"))
POLL_APPROACHING = int(os.getenv("POLL_APPROACHING", "120"))
POLL_ACTIVE = int(os.getenv("POLL_ACTIVE", "30"))

NOTIFY_MINUTES_BEFORE = int(os.getenv("NOTIFY_MINUTES_BEFORE", "2"))

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

NOTIFICATION_BACKEND = os.getenv("NOTIFICATION_BACKEND", "native")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Zurich")
