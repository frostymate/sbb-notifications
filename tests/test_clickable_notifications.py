"""Tests for clickable notification URLs — build_sbb_url + notifier url param."""

import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from transport_client import build_sbb_url
from sbb_parser import Journey, Leg, Stop
from main import JourneyMonitor

TZ = ZoneInfo("Europe/Zurich")


class TestBuildSbbUrl(unittest.TestCase):
    """Test SBB timetable URL construction."""

    def test_basic_url(self):
        dt = datetime(2026, 4, 18, 8, 30, tzinfo=TZ)
        url = build_sbb_url("Zürich HB", "Bern", dt)
        self.assertIn("sbb.ch", url)
        self.assertIn("from=Z%C3%BCrich%20HB", url)
        self.assertIn("to=Bern", url)
        self.assertIn("date=2026-04-18", url)
        self.assertIn("time=08:30", url)

    def test_special_characters_encoded(self):
        dt = datetime(2026, 6, 1, 14, 0, tzinfo=TZ)
        url = build_sbb_url("Genève-Aéroport", "St. Gallen", dt)
        self.assertIn("Gen%C3%A8ve", url)
        self.assertIn("St.%20Gallen", url)

    def test_returns_string(self):
        dt = datetime(2026, 1, 1, 0, 0, tzinfo=TZ)
        url = build_sbb_url("A", "B", dt)
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith("https://"))


class TestJourneyMonitorSbbUrl(unittest.TestCase):
    """Test that JourneyMonitor.sbb_url is built correctly."""

    def _make_monitor(self):
        now = datetime.now(TZ)
        journey = Journey(
            origin="Lausanne",
            destination="Zürich HB",
            departure=now,
            arrival=now,
            legs=[],
        )
        return JourneyMonitor(journey)

    def test_sbb_url_property(self):
        monitor = self._make_monitor()
        url = monitor.sbb_url
        self.assertIn("from=Lausanne", url)
        self.assertIn("to=Z%C3%BCrich%20HB", url)


class TestSendNotificationWithUrl(unittest.TestCase):
    """Test that send_notification passes url through to platform-specific senders."""

    @patch("notifier.platform")
    @patch("notifier.subprocess")
    def test_windows_toast_receives_url(self, mock_subprocess, mock_platform):
        mock_platform.system.return_value = "Windows"
        mock_subprocess.run.return_value = MagicMock()

        from notifier import send_notification
        send_notification("Title", "Body", url="https://www.sbb.ch/test")

        args = mock_subprocess.run.call_args
        ps_command = args[0][0][-1]  # last element is the PowerShell script
        self.assertIn('launch="https://www.sbb.ch/test"', ps_command)
        self.assertIn('activationType="protocol"', ps_command)

    @patch("notifier.platform")
    @patch("notifier.subprocess")
    def test_windows_toast_no_url(self, mock_subprocess, mock_platform):
        mock_platform.system.return_value = "Windows"
        mock_subprocess.run.return_value = MagicMock()

        from notifier import send_notification
        send_notification("Title", "Body")

        args = mock_subprocess.run.call_args
        ps_command = args[0][0][-1]
        self.assertNotIn("launch=", ps_command)

    @patch("notifier.platform")
    @patch("notifier.subprocess")
    def test_linux_url_appended_to_body(self, mock_subprocess, mock_platform):
        mock_platform.system.return_value = "Linux"
        mock_subprocess.run.return_value = MagicMock()

        from notifier import send_notification
        send_notification("Title", "Body", url="https://www.sbb.ch/test")

        args = mock_subprocess.run.call_args
        cmd = args[0][0]
        # The body (last argument) should contain the URL
        self.assertIn("https://www.sbb.ch/test", cmd[-1])


class TestCheckAndNotifyPassesUrl(unittest.TestCase):
    """Integration: JourneyMonitor.check_and_notify passes sbb_url to notifications."""

    @patch("main.send_notification")
    def test_arrival_notification_includes_url(self, mock_notify):
        now = datetime.now(TZ)
        leg = Leg(
            from_station="Bern",
            to_station="Zürich HB",
            departure=now - __import__("datetime").timedelta(minutes=30),
            arrival=now + __import__("datetime").timedelta(minutes=1),
            train_type="IC",
            train_number="708",
            arrival_platform="3",
        )
        journey = Journey(
            origin="Bern",
            destination="Zürich HB",
            departure=now - __import__("datetime").timedelta(minutes=30),
            arrival=now + __import__("datetime").timedelta(minutes=1),
            legs=[leg],
        )
        monitor = JourneyMonitor(journey)
        monitor.enriched = True
        monitor.check_and_notify(now)

        mock_notify.assert_called()
        call_kwargs = mock_notify.call_args
        self.assertIn("url", call_kwargs.kwargs)
        self.assertIn("sbb.ch", call_kwargs.kwargs["url"])
        self.assertIn("from=Bern", call_kwargs.kwargs["url"])

    @patch("main.send_notification")
    def test_transfer_notification_includes_url(self, mock_notify):
        from datetime import timedelta
        now = datetime.now(TZ)
        leg1 = Leg(
            from_station="Lausanne",
            to_station="Bern",
            departure=now - timedelta(minutes=30),
            arrival=now + timedelta(minutes=1),
            train_type="IC",
            train_number="1",
            arrival_platform="7",
        )
        leg2 = Leg(
            from_station="Bern",
            to_station="Zürich HB",
            departure=now + timedelta(minutes=5),
            arrival=now + timedelta(minutes=35),
            train_type="IC",
            train_number="708",
            departure_platform="3",
        )
        journey = Journey(
            origin="Lausanne",
            destination="Zürich HB",
            departure=now - timedelta(minutes=30),
            arrival=now + timedelta(minutes=35),
            legs=[leg1, leg2],
        )
        monitor = JourneyMonitor(journey)
        monitor.enriched = True
        monitor.check_and_notify(now)

        mock_notify.assert_called()
        call_kwargs = mock_notify.call_args
        self.assertIn("url", call_kwargs.kwargs)
        self.assertIn("sbb.ch", call_kwargs.kwargs["url"])

    @patch("main.send_notification")
    def test_delay_notification_includes_url(self, mock_notify):
        from datetime import timedelta
        now = datetime.now(TZ)
        old_leg = Leg(
            from_station="Bern",
            to_station="Zürich HB",
            departure=now + timedelta(minutes=10),
            arrival=now + timedelta(minutes=40),
            train_type="IC",
            train_number="708",
            departure_delay=0,
        )
        new_leg = Leg(
            from_station="Bern",
            to_station="Zürich HB",
            departure=now + timedelta(minutes=10),
            arrival=now + timedelta(minutes=40),
            train_type="IC",
            train_number="708",
            departure_delay=5,
        )
        journey = Journey(
            origin="Bern",
            destination="Zürich HB",
            departure=now,
            arrival=now + timedelta(minutes=40),
            legs=[new_leg],
        )
        monitor = JourneyMonitor(journey)
        monitor.enriched = True
        monitor._check_changes([old_leg])

        mock_notify.assert_called()
        call_kwargs = mock_notify.call_args
        self.assertIn("url", call_kwargs.kwargs)
        self.assertIn("sbb.ch", call_kwargs.kwargs["url"])


if __name__ == "__main__":
    unittest.main()
