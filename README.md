# 🚆 SBB-Not — Swiss Transit Arrival Reminder

Never miss your stop again! SBB-Not monitors your Google Calendar for SBB journey events and sends desktop notifications before your arrival or transfer.

## How It Works

```
📱 SBB App → "Add to Calendar" → Google Calendar
    ↓ (syncs automatically)
💻 SBB-Not daemon reads your calendar → fetches real-time data → notifies you
```

1. Plan your route in the SBB app as usual
2. Tap **"Add to Calendar"** — the event syncs to Google Calendar
3. SBB-Not detects the event, fetches the full route with real-time delays
4. You get a desktop notification **2 minutes before** your stop or transfer

## Features

- 🔔 **Arrival alerts** — notified before your destination
- 🔄 **Transfer alerts** — notified before you need to switch trains
- ⏱️ **Real-time delays** — uses live data from transport.opendata.ch
- 📅 **Adaptive polling** — polls faster as your trip approaches
- 🖥️ **Cross-platform** — works on Linux (`notify-send`) and macOS (`osascript`)

## Setup

### 1. Google Calendar API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Calendar API**
3. Create **OAuth 2.0 Client ID** (Desktop app)
4. Download the JSON → save as `credentials.json` in this directory

### 2. Configure

```bash
cp .env.example .env
# Edit .env if you want to change notification timing, timezone, etc.
```

### 3. Install & Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib httpx python-dotenv
python main.py
```

On first run, it opens a browser for Google OAuth. After that, the token is cached.

### 4. Add SBB Trips to Calendar

In the SBB app, after searching a route, tap **"Add to Calendar"**. SBB-Not will detect it automatically.

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_IDLE` | 300 | Seconds between polls when no trip is near |
| `POLL_APPROACHING` | 120 | Seconds between polls when trip is within 2h |
| `POLL_ACTIVE` | 30 | Seconds between polls during active journey |
| `NOTIFY_MINUTES_BEFORE` | 2 | Minutes before stop to send notification |
| `GOOGLE_CALENDAR_ID` | primary | Which calendar to watch |
| `TIMEZONE` | Europe/Zurich | Your timezone |

## How Events Are Detected

SBB-Not identifies SBB events by looking for:
- Swiss station names (Zürich, Bern, Basel, etc.)
- Train type codes (IC, IR, RE, S-Bahn)
- "Origin - Destination" title pattern
- SBB/CFF/FFS keywords

## Architecture

```
calendar_client.py  → Google Calendar API polling
sbb_parser.py       → Parse SBB events into Journey/Leg/Stop objects
transport_client.py → Fetch real-time data from transport.opendata.ch
notifier.py         → Cross-platform desktop notifications
main.py             → Daemon: adaptive polling + journey monitoring
config.py           → Environment configuration
```
