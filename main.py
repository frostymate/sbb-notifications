"""SBB-Not — Swiss public transport arrival reminder daemon.

Monitors your Google Calendar for SBB journey events and sends desktop
notifications before your arrival or transfer.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import (
    POLL_IDLE, POLL_APPROACHING, POLL_ACTIVE,
    NOTIFY_MINUTES_BEFORE, TIMEZONE,
)
from calendar_client import get_calendar_service, fetch_upcoming_events
from sbb_parser import parse_event, Journey, Leg
from transport_client import fetch_connection, find_best_connection, connection_to_legs
from notifier import send_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sbb-not")

TZ = ZoneInfo(TIMEZONE)


class JourneyMonitor:
    """Monitors a single active journey."""

    def __init__(self, journey: Journey):
        self.journey = journey
        self.enriched = False
        self.notified_stops: set[str] = set()  # "leg_idx:stop_name" to avoid duplicates
        self.notified_arrival = False
        self.notified_delays: dict[str, int] = {}  # key → last notified delay
        self.last_refresh: datetime | None = None
        self.refresh_interval = timedelta(minutes=2)  # re-fetch real-time data every 2 min

    async def enrich_with_realtime(self) -> None:
        """Fetch full stop list + real-time data from transport API."""
        try:
            connections = await fetch_connection(
                self.journey.origin,
                self.journey.destination,
                self.journey.departure,
            )
            if not connections:
                logger.warning(f"No connections found for {self.journey.origin} → {self.journey.destination}")
                return

            best = find_best_connection(connections, self.journey.departure)
            if not best:
                return

            self.journey.legs = connection_to_legs(best)
            self.enriched = True
            self.last_refresh = datetime.now(TZ)
            total_stops = sum(len(leg.intermediate_stops) for leg in self.journey.legs)
            logger.info(
                f"✅ Enriched journey: {self.journey.origin} → {self.journey.destination} "
                f"({len(self.journey.legs)} legs, {total_stops} stops)"
            )
        except Exception as e:
            logger.error(f"Failed to enrich journey: {e}")

    async def refresh_if_needed(self, now: datetime) -> None:
        """Re-fetch real-time data periodically to catch delays and platform changes."""
        if not self.enriched:
            return
        if self.last_refresh and (now - self.last_refresh) < self.refresh_interval:
            return
        logger.info(f"🔄 Refreshing real-time data for {self.journey.origin} → {self.journey.destination}")
        old_legs = self.journey.legs
        await self.enrich_with_realtime()
        self._check_changes(old_legs)

    def _check_changes(self, old_legs: list[Leg]) -> None:
        """Compare old vs new legs and notify about delay/platform changes."""
        for leg_idx, (old, new) in enumerate(zip(old_legs, self.journey.legs)):
            # Platform changes
            if old.departure_platform and new.departure_platform and old.departure_platform != new.departure_platform:
                send_notification(
                    "⚠️ Platform change!",
                    f"{new.train_type or ''} {new.train_number or ''} at {new.from_station}: "
                    f"Gl. {old.departure_platform} → Gl. {new.departure_platform}",
                    urgency="critical",
                )
                logger.info(f"⚠️ Platform change at {new.from_station}: {old.departure_platform} → {new.departure_platform}")

            if old.arrival_platform and new.arrival_platform and old.arrival_platform != new.arrival_platform:
                send_notification(
                    "⚠️ Platform change!",
                    f"Arrival at {new.to_station}: Gl. {old.arrival_platform} → Gl. {new.arrival_platform}",
                    urgency="critical",
                )
                logger.info(f"⚠️ Platform change at {new.to_station}: {old.arrival_platform} → {new.arrival_platform}")

            # Delay changes (notify if delay increased by 3+ min)
            delay_key = f"{leg_idx}:delay:{new.from_station}"
            new_delay = new.departure_delay or 0
            prev_delay = self.notified_delays.get(delay_key, 0)
            if new_delay >= 3 and new_delay - prev_delay >= 3:
                send_notification(
                    "⏱️ Delay update",
                    f"{new.train_type or ''} {new.train_number or ''} from {new.from_station}: "
                    f"+{new_delay} min delay",
                    urgency="critical",
                )
                self.notified_delays[delay_key] = new_delay
                logger.info(f"⏱️ Delay: {new.from_station} +{new_delay} min")

    def _format_platform(self, platform: str | None) -> str:
        """Format platform info for display."""
        return f" (Gl. {platform})" if platform else ""

    def check_and_notify(self, now: datetime) -> None:
        """Check if any upcoming stops/transfers need a notification."""
        notify_delta = timedelta(minutes=NOTIFY_MINUTES_BEFORE)

        for leg_idx, leg in enumerate(self.journey.legs):
            # Notify before transfers (arrival at end of each non-final leg)
            if leg_idx < len(self.journey.legs) - 1:
                transfer_key = f"{leg_idx}:transfer:{leg.to_station}"
                if transfer_key not in self.notified_stops:
                    time_until = leg.arrival - now
                    if timedelta(0) < time_until <= notify_delta:
                        next_leg = self.journey.legs[leg_idx + 1]
                        platform_info = self._format_platform(next_leg.departure_platform)
                        delay_info = f" (+{next_leg.departure_delay} min)" if next_leg.departure_delay else ""
                        send_notification(
                            "🔄 Transfer coming up!",
                            f"Arriving at {leg.to_station}{self._format_platform(leg.arrival_platform)} in ~{int(time_until.total_seconds() / 60)} min.\n"
                            f"Next: {next_leg.train_type or ''} {next_leg.train_number or ''} → {next_leg.to_station}{platform_info}{delay_info}",
                            urgency="critical",
                        )
                        self.notified_stops.add(transfer_key)
                        logger.info(f"🔄 Notified: transfer at {leg.to_station}")

            # Notify before intermediate stops (if user wants per-stop alerts)
            for stop in leg.intermediate_stops:
                if not stop.arrival:
                    continue
                stop_key = f"{leg_idx}:stop:{stop.name}"
                if stop_key in self.notified_stops:
                    continue

        # Notify before final arrival
        if not self.notified_arrival:
            final_leg = self.journey.legs[-1] if self.journey.legs else None
            if final_leg:
                time_until = final_leg.arrival - now
                if timedelta(0) < time_until <= notify_delta:
                    platform_info = self._format_platform(final_leg.arrival_platform)
                    delay_info = f" (+{final_leg.arrival_delay} min late)" if final_leg.arrival_delay else ""
                    send_notification(
                        "🎯 Arriving soon!",
                        f"{self.journey.destination}{platform_info} in ~{int(time_until.total_seconds() / 60)} min.{delay_info} "
                        f"Get ready to exit!",
                        urgency="critical",
                    )
                    self.notified_arrival = True
                    logger.info(f"🎯 Notified: arriving at {self.journey.destination}")

    def is_finished(self, now: datetime) -> bool:
        """Is this journey in the past?"""
        return now > self.journey.arrival + timedelta(minutes=5)


class SBBNotDaemon:
    """Main daemon — polls calendar, manages journey monitors."""

    def __init__(self):
        self.calendar_service = None
        self.monitors: dict[str, JourneyMonitor] = {}  # event_id → monitor

    def _get_poll_interval(self, now: datetime) -> int:
        """Adaptive polling: faster when a trip is near."""
        if not self.monitors:
            return POLL_IDLE

        soonest = min(m.journey.departure for m in self.monitors.values())
        time_until = (soonest - now).total_seconds()

        if time_until < 0:
            return POLL_ACTIVE  # journey in progress
        elif time_until < 7200:  # within 2 hours
            return POLL_APPROACHING
        else:
            return POLL_IDLE

    async def poll_calendar(self) -> None:
        """Check calendar for new SBB events."""
        try:
            events = fetch_upcoming_events(self.calendar_service)
        except Exception as e:
            logger.error(f"Calendar poll failed: {e}")
            return

        for event in events:
            eid = event.get("id", "")
            if eid in self.monitors:
                continue

            journey = parse_event(event)
            if journey:
                monitor = JourneyMonitor(journey)
                self.monitors[eid] = monitor
                logger.info(
                    f"📅 New journey detected: {journey.origin} → {journey.destination} "
                    f"at {journey.departure.strftime('%H:%M')}"
                )
                await monitor.enrich_with_realtime()

    async def run(self) -> None:
        """Main loop."""
        logger.info("🚆 SBB-Not starting...")
        logger.info("Authenticating with Google Calendar...")

        try:
            self.calendar_service = get_calendar_service()
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)

        logger.info("✅ Connected to Google Calendar")
        logger.info(f"Watching for SBB events (notify {NOTIFY_MINUTES_BEFORE} min before stops)")
        logger.info("Press Ctrl+C to stop\n")

        send_notification("🚆 SBB-Not", "Monitoring your calendar for train journeys...")

        while True:
            now = datetime.now(TZ)

            # Poll calendar
            await self.poll_calendar()

            # Check all active monitors
            finished = []
            for eid, monitor in self.monitors.items():
                if monitor.is_finished(now):
                    finished.append(eid)
                    continue

                if not monitor.enriched:
                    await monitor.enrich_with_realtime()
                else:
                    await monitor.refresh_if_needed(now)

                monitor.check_and_notify(now)

            # Clean up finished journeys
            for eid in finished:
                j = self.monitors[eid].journey
                logger.info(f"✅ Journey complete: {j.origin} → {j.destination}")
                del self.monitors[eid]

            # Adaptive sleep
            interval = self._get_poll_interval(now)
            active = len(self.monitors)
            if active:
                logger.debug(f"Monitoring {active} journey(s), next poll in {interval}s")
            await asyncio.sleep(interval)


def main():
    daemon = SBBNotDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("\n👋 SBB-Not stopped. Safe travels!")


if __name__ == "__main__":
    main()
