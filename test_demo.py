"""Demo script — triggers real notifications with dummy SBB journey data."""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sbb_parser import Journey, Leg, Stop
from notifier import send_notification
from main import JourneyMonitor

TZ = ZoneInfo("Europe/Zurich")
now = datetime.now(TZ)


def demo_notifications():
    """Show what each notification type looks like."""
    print("=" * 60)
    print("Gleis Notification Demo")
    print("=" * 60)

    # 1. Startup notification
    print("\n[1/5] Startup notification...")
    send_notification("🚆 Gleis", "Monitoring your calendar for train journeys...")
    time.sleep(2)

    # 2. Transfer notification with platform
    print("[2/5] Transfer notification (with platform)...")
    send_notification(
        "🔄 Transfer coming up!",
        "Arriving at Bern (Gl. 7) in ~2 min.\nNext: IC 708 → Zürich HB (Gl. 3)",
        urgency="critical",
    )
    time.sleep(2)

    # 3. Arrival notification with platform
    print("[3/5] Arrival notification (with platform)...")
    send_notification(
        "🎯 Arriving soon!",
        "Zürich HB (Gl. 3) in ~2 min. Get ready to exit!",
        urgency="critical",
    )
    time.sleep(2)

    # 4. Delay alert
    print("[4/5] Delay alert...")
    send_notification(
        "⏱️ Delay update",
        "IC 708 from Bern: +5 min delay",
        urgency="critical",
    )
    time.sleep(2)

    # 5. Platform change alert
    print("[5/5] Platform change alert...")
    send_notification(
        "⚠️ Platform change!",
        "IC 708 at Bern: Gl. 7 → Gl. 12",
        urgency="critical",
    )
    print("\n✅ All 5 notification types sent!\n")


def demo_journey_monitor():
    """Simulate a full journey with platforms and delays."""
    print("=" * 60)
    print("Journey Monitor Simulation")
    print("=" * 60)

    # 2-leg journey: Lausanne → Bern → Zürich HB
    # Leg 1 arrives in ~1.5 min (triggers transfer alert with platform)
    leg1_dep = now - timedelta(minutes=30)
    leg1_arr = now + timedelta(minutes=1, seconds=30)

    leg2_dep = now + timedelta(minutes=5)
    leg2_arr = now + timedelta(minutes=35)

    leg1 = Leg(
        from_station="Lausanne",
        to_station="Bern",
        departure=leg1_dep,
        arrival=leg1_arr,
        train_type="IC",
        train_number="1",
        intermediate_stops=[
            Stop(name="Fribourg/Freiburg", arrival=now - timedelta(minutes=10),
                 departure=now - timedelta(minutes=9), platform="2"),
        ],
        departure_platform="5",
        arrival_platform="7",
        departure_delay=None,
        arrival_delay=2,
    )
    leg2 = Leg(
        from_station="Bern",
        to_station="Zürich HB",
        departure=leg2_dep,
        arrival=leg2_arr,
        train_type="IC",
        train_number="708",
        intermediate_stops=[
            Stop(name="Aarau", arrival=now + timedelta(minutes=20),
                 departure=now + timedelta(minutes=21), platform="4"),
        ],
        departure_platform="3",
        arrival_platform="16",
        departure_delay=5,
        arrival_delay=5,
    )

    journey = Journey(
        origin="Lausanne",
        destination="Zürich HB",
        departure=leg1_dep,
        arrival=leg2_arr,
        legs=[leg1, leg2],
        raw_title="IC 1 Lausanne - Zürich HB",
    )

    monitor = JourneyMonitor(journey)
    monitor.enriched = True

    print(f"\nJourney: {journey.origin} → {journey.destination}")
    print(f"  Leg 1: IC 1  Lausanne (Gl. 5) → Bern (Gl. 7)  [+2 min late]")
    print(f"  Leg 2: IC 708 Bern (Gl. 3) → Zürich HB (Gl. 16)  [+5 min delay]")
    print(f"\nRunning monitor check...")

    monitor.check_and_notify(now)

    if monitor.notified_stops:
        print(f"  → Transfer notification triggered: {monitor.notified_stops}")
    else:
        print("  → No transfer notification (arrival > 2 min away)")

    # Simulate platform change detection
    print("\nSimulating platform change (Bern Gl. 3 → Gl. 12)...")
    old_legs = journey.legs.copy()
    leg2_changed = Leg(
        from_station="Bern",
        to_station="Zürich HB",
        departure=leg2_dep,
        arrival=leg2_arr,
        train_type="IC",
        train_number="708",
        intermediate_stops=leg2.intermediate_stops,
        departure_platform="12",  # changed from 3!
        arrival_platform="16",
        departure_delay=7,  # increased from 5
        arrival_delay=7,
    )
    journey.legs = [leg1, leg2_changed]
    monitor._check_changes(old_legs)

    print("\nDone!")


if __name__ == "__main__":
    demo_notifications()
    print()
    demo_journey_monitor()
