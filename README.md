# 🚆 Gleis — Swiss Transit Arrival Reminder

Never miss your stop again! Gleis monitors your Google Calendar for SBB journey events and sends desktop notifications before your arrival or transfer.

## How It Works

```
📱 SBB App → "Add to Calendar" → Google Calendar
    ↓ (syncs automatically)
💻 Gleis daemon reads your calendar → fetches real-time data → notifies you
```

1. Plan your route in the SBB app as usual
2. Tap **"Add to Calendar"** — the event syncs to Google Calendar
3. Gleis detects the event, fetches the full route with real-time delays
4. You get a desktop notification **2 minutes before** your stop or transfer

## Features

- 🔔 **Arrival alerts** — notified before your destination
- 🔄 **Transfer alerts** — notified before you need to switch trains
- ⏱️ **Real-time delays** — uses live data from transport.opendata.ch
- 📅 **Adaptive polling** — polls faster as your trip approaches
- 🖥️ **Cross-platform** — works on Windows (toast notifications), Linux (`notify-send`), and macOS (`osascript`)

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
source venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib httpx python-dotenv tzdata
python main.py
```

On first run, you'll be prompted to complete Google OAuth in the browser. After that, the token is cached.

### Run in Background (Windows)

To run Gleis automatically at login as a background service:

```powershell
# Register scheduled task (one-time setup)
powershell -ExecutionPolicy Bypass -File .\install_task.ps1

# Start immediately
Start-ScheduledTask -TaskName "Gleis"
```

The task starts at every login, runs silently, and auto-restarts on failure.

```powershell
# Manage the task
Get-ScheduledTask -TaskName "Gleis"          # Check status
Stop-ScheduledTask -TaskName "Gleis"         # Stop
Start-ScheduledTask -TaskName "Gleis"        # Start
Unregister-ScheduledTask -TaskName "Gleis"   # Remove
```

### 4. Add SBB Trips to Calendar

In the SBB app, after searching a route, tap **"Add to Calendar"**. Gleis will detect it automatically.

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

Gleis identifies SBB events by looking for:
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
