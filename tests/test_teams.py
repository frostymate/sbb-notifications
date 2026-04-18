"""Tests for Teams/Outlook calendar integration and backend selection."""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from teams_calendar_client import _convert_to_gcal_format, _graph_datetime_to_iso
from sbb_parser import parse_event, is_sbb_event, parse_title


class TestGraphDatetimeConversion(unittest.TestCase):
    """Test _graph_datetime_to_iso edge cases."""

    def test_zurich_timezone(self):
        result = _graph_datetime_to_iso("2026-04-18T08:30:00.0000000", "Europe/Zurich")
        dt = datetime.fromisoformat(result)
        self.assertEqual(dt.hour, 8)
        self.assertEqual(dt.minute, 30)
        self.assertIsNotNone(dt.tzinfo)

    def test_utc_timezone(self):
        result = _graph_datetime_to_iso("2026-04-18T06:30:00.0000000", "UTC")
        dt = datetime.fromisoformat(result)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_empty_string(self):
        self.assertEqual(_graph_datetime_to_iso("", "UTC"), "")

    def test_no_fractional_seconds(self):
        result = _graph_datetime_to_iso("2026-04-18T10:00:00", "Europe/Zurich")
        dt = datetime.fromisoformat(result)
        self.assertEqual(dt.hour, 10)

    def test_trailing_zeros_stripped(self):
        result = _graph_datetime_to_iso("2026-04-18T10:15:30.1230000", "UTC")
        dt = datetime.fromisoformat(result)
        self.assertEqual(dt.minute, 15)
        self.assertEqual(dt.second, 30)


class TestConvertToGcalFormat(unittest.TestCase):
    """Test Microsoft Graph → Google Calendar format conversion."""

    def _make_ms_event(self, **overrides):
        base = {
            "id": "AAMkAGI2T",
            "subject": "Zürich HB - Bern",
            "bodyPreview": "IC 708 Gleis 3",
            "body": {"content": "IC 708 Gleis 3", "contentType": "text"},
            "start": {"dateTime": "2026-04-18T08:30:00.0000000", "timeZone": "Europe/Zurich"},
            "end": {"dateTime": "2026-04-18T09:26:00.0000000", "timeZone": "Europe/Zurich"},
            "location": {"displayName": "Zürich HB"},
            "categories": [],
        }
        base.update(overrides)
        return base

    def test_basic_conversion(self):
        ms_event = self._make_ms_event()
        result = _convert_to_gcal_format(ms_event)

        self.assertEqual(result["id"], "AAMkAGI2T")
        self.assertEqual(result["summary"], "Zürich HB - Bern")
        self.assertEqual(result["description"], "IC 708 Gleis 3")
        self.assertEqual(result["location"], "Zürich HB")
        self.assertIn("dateTime", result["start"])
        self.assertIn("dateTime", result["end"])

    def test_start_end_parseable(self):
        ms_event = self._make_ms_event()
        result = _convert_to_gcal_format(ms_event)

        start = datetime.fromisoformat(result["start"]["dateTime"])
        end = datetime.fromisoformat(result["end"]["dateTime"])
        self.assertGreater(end, start)

    def test_empty_body_preview_falls_back_to_body(self):
        ms_event = self._make_ms_event(bodyPreview="", body={"content": "Fallback body"})
        result = _convert_to_gcal_format(ms_event)
        self.assertEqual(result["description"], "Fallback body")

    def test_location_as_string(self):
        ms_event = self._make_ms_event(location="Plain string location")
        result = _convert_to_gcal_format(ms_event)
        self.assertEqual(result["location"], "Plain string location")

    def test_missing_location(self):
        ms_event = self._make_ms_event(location={})
        result = _convert_to_gcal_format(ms_event)
        self.assertEqual(result["location"], "")


class TestTeamsEventParsesBySbbParser(unittest.TestCase):
    """End-to-end: Teams events (after conversion) are correctly parsed by sbb_parser."""

    def _make_converted_event(self, summary, description="", location=""):
        """Simulate a Teams event already converted to gcal format."""
        return {
            "id": "teams-event-123",
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": "2026-04-18T08:30:00+02:00"},
            "end": {"dateTime": "2026-04-18T09:26:00+02:00"},
        }

    def test_sbb_event_detected(self):
        event = self._make_converted_event("Zürich HB - Bern")
        self.assertTrue(is_sbb_event(event))

    def test_sbb_event_with_train_type(self):
        event = self._make_converted_event("IC 708 Zürich HB - Bern")
        self.assertTrue(is_sbb_event(event))

    def test_non_sbb_event_rejected(self):
        event = self._make_converted_event("Team standup meeting")
        self.assertFalse(is_sbb_event(event))

    def test_parse_event_returns_journey(self):
        event = self._make_converted_event("Zürich HB - Bern", description="SBB Gleis 3")
        journey = parse_event(event)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.origin, "Zürich HB")
        self.assertEqual(journey.destination, "Bern")
        self.assertEqual(len(journey.legs), 1)
        self.assertEqual(journey.event_id, "teams-event-123")

    def test_parse_event_with_train_info(self):
        event = self._make_converted_event("IC 708 Zürich HB - Bern")
        journey = parse_event(event)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.legs[0].train_type, "IC")
        self.assertEqual(journey.legs[0].train_number, "708")

    def test_parse_event_times_correct(self):
        event = self._make_converted_event("Zürich HB - Bern")
        journey = parse_event(event)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.departure.hour, 8)
        self.assertEqual(journey.departure.minute, 30)
        self.assertEqual(journey.arrival.hour, 9)
        self.assertEqual(journey.arrival.minute, 26)

    def test_parse_event_with_sbahn(self):
        event = self._make_converted_event("S8 Zürich HB - Winterthur")
        journey = parse_event(event)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.legs[0].train_type, "S")
        self.assertEqual(journey.legs[0].train_number, "8")

    def test_non_sbb_returns_none(self):
        event = self._make_converted_event("Team standup meeting")
        journey = parse_event(event)
        self.assertIsNone(journey)


class TestCalendarBackendSelection(unittest.TestCase):
    """Test that main.py selects the correct calendar backend."""

    @patch("main.CALENDAR_BACKEND", "teams")
    def test_backend_teams_selected(self):
        from main import SBBNotDaemon
        daemon = SBBNotDaemon()
        daemon.backend = "teams"
        self.assertEqual(daemon.backend, "teams")

    @patch("main.CALENDAR_BACKEND", "google")
    def test_backend_google_selected(self):
        from main import SBBNotDaemon
        daemon = SBBNotDaemon()
        daemon.backend = "google"
        self.assertEqual(daemon.backend, "google")


class TestTeamsEventFetchMocked(unittest.TestCase):
    """Test fetch_upcoming_events with mocked HTTP and auth."""

    @patch("teams_calendar_client._get_access_token", return_value="fake-token")
    @patch("httpx.Client")
    def test_fetch_returns_converted_events(self, mock_client_cls, mock_token):
        from teams_calendar_client import fetch_upcoming_events

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "value": [
                {
                    "id": "ev1",
                    "subject": "Bern - Basel SBB",
                    "bodyPreview": "IC 6 Gleis 5",
                    "body": {"content": "IC 6 Gleis 5"},
                    "start": {"dateTime": "2026-04-18T10:00:00.0000000", "timeZone": "Europe/Zurich"},
                    "end": {"dateTime": "2026-04-18T10:55:00.0000000", "timeZone": "Europe/Zurich"},
                    "location": {"displayName": "Bern"},
                    "categories": [],
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        events = fetch_upcoming_events(hours_ahead=6)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"], "Bern - Basel SBB")
        self.assertEqual(events[0]["description"], "IC 6 Gleis 5")

        # Verify the converted event can be parsed by sbb_parser
        journey = parse_event(events[0])
        self.assertIsNotNone(journey)
        self.assertEqual(journey.origin, "Bern")
        self.assertEqual(journey.destination, "Basel SBB")

    @patch("teams_calendar_client._get_access_token", return_value="fake-token")
    @patch("httpx.Client")
    def test_fetch_empty_calendar(self, mock_client_cls, mock_token):
        from teams_calendar_client import fetch_upcoming_events

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        events = fetch_upcoming_events(hours_ahead=6)
        self.assertEqual(events, [])

    @patch("teams_calendar_client._get_access_token", return_value="fake-token")
    @patch("httpx.Client")
    def test_fetch_uses_specific_calendar_id(self, mock_client_cls, mock_token):
        from teams_calendar_client import fetch_upcoming_events

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"value": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with patch("teams_calendar_client.MS_CALENDAR_ID", "my-cal-id"):
            fetch_upcoming_events(hours_ahead=6)

        call_args = mock_client.get.call_args
        self.assertIn("my-cal-id", call_args[0][0])


class TestGraphHeadersAuth(unittest.TestCase):
    """Test auth header construction."""

    @patch("teams_calendar_client._get_access_token", return_value="test-bearer-token")
    def test_headers_contain_bearer(self, mock_token):
        from teams_calendar_client import get_graph_headers
        headers = get_graph_headers()
        self.assertEqual(headers["Authorization"], "Bearer test-bearer-token")
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
