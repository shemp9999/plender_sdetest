import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from main import _build_point, _write_point
from influxdb_manager import InfluxDBClientManager
from wttr_manager import Wttr

class TestWeatherDataProcessing(unittest.TestCase):

    def test_build_point(self):
        data = {
            "current_condition": [{
                "localObsDateTime": "2025-04-21 11:55 AM",
                "temp_C": "20",
                "humidity": "74",
                "pressureInches": "30"
            }],
            "nearest_area": [{
                "latitude": "12.34",
                "longitude": "56.78"
            }]
        }
        city_info = {"city": "TestCity", "country": "TestCountry", "tz": "UTC"}
        measurements = {
            "temp_celsius": "temp_C",
            "temp_kelvin": "temp_K",
            "humidity": "humidity",
            "pressure": "pressureInches"
        }

        # Mock wttr object with parse_observation_time method
        mock_wttr = MagicMock()
        mock_wttr.parse_observation_time.return_value = datetime(2025, 4, 21, 11, 55)

        point, missing_fields, city, timestamp = _build_point(data, city_info, measurements, mock_wttr)

        self.assertIsNotNone(point)
        self.assertEqual(city, "TestCity")
        self.assertEqual(timestamp, "2025-04-21T11:55:00Z")
        self.assertEqual(len(missing_fields), 0)

    def test_build_point_invalid_timestamp(self):
        data = {
            "current_condition": [{
                "localObsDateTime": "INVALID",
                "temp_C": "20"
            }],
            "nearest_area": [{"latitude": "12.34"}]
        }
        city_info = {"city": "TestCity", "country": "TestCountry", "tz": "UTC"}
        measurements = {"temp_celsius": "temp_C"}

        # Mock wttr object that returns None for invalid timestamp
        mock_wttr = MagicMock()
        mock_wttr.parse_observation_time.return_value = None

        point, missing_fields, city, timestamp = _build_point(data, city_info, measurements, mock_wttr)

        self.assertIsNone(point)
        self.assertEqual(city, "TestCity")
        self.assertIsNone(timestamp)
        self.assertEqual(len(missing_fields), 0)

    @patch('influxdb_manager.InfluxDBClientManager')
    def test_write_point_success(self, MockInfluxDBClientManager):
        mock_manager = MockInfluxDBClientManager()
        mock_manager.write_data.return_value = True

        from influxdb_client import Point
        point = Point("weather_data").tag("city", "TestCity").field("temp", 20.0)

        last_seen = {}
        result = _write_point(mock_manager, point, "TestCity", "2025-04-21T11:55:00Z", [], last_seen)

        mock_manager.write_data.assert_called_once()
        self.assertTrue(result)
        self.assertEqual(last_seen["TestCity"], "2025-04-21T11:55:00Z")

    @patch('influxdb_manager.InfluxDBClientManager')
    def test_write_point_new_timestamp(self, MockInfluxDBClientManager):
        """Test that new timestamps trigger INFO log and update last_seen."""
        mock_manager = MockInfluxDBClientManager()
        mock_manager.write_data.return_value = True

        from influxdb_client import Point
        point = Point("weather_data").tag("city", "TestCity").field("temp", 20.0)

        last_seen = {}

        with self.assertLogs(level='INFO') as log:
            result = _write_point(mock_manager, point, "TestCity", "2025-04-21T11:55:00Z", [], last_seen)

        self.assertTrue(result)
        self.assertIn("Recorded TestCity", log.output[0])
        self.assertEqual(last_seen["TestCity"], "2025-04-21T11:55:00Z")

    @patch('influxdb_manager.InfluxDBClientManager')
    def test_write_point_duplicate_timestamp(self, MockInfluxDBClientManager):
        """Test that duplicate timestamps don't trigger INFO log."""
        mock_manager = MockInfluxDBClientManager()
        mock_manager.write_data.return_value = True

        from influxdb_client import Point
        point = Point("weather_data").tag("city", "TestCity").field("temp", 20.0)

        # Simulate timestamp already seen
        last_seen = {"TestCity": "2025-04-21T11:55:00Z"}

        # Capture logs at INFO level - should NOT contain "Recorded" for duplicate
        with self.assertLogs(level='DEBUG') as log:
            result = _write_point(mock_manager, point, "TestCity", "2025-04-21T11:55:00Z", [], last_seen)

        self.assertTrue(result)
        # Check that DEBUG log contains "Re-wrote" message
        self.assertIn("Re-wrote TestCity", ''.join(log.output))
        # Timestamp should remain unchanged
        self.assertEqual(last_seen["TestCity"], "2025-04-21T11:55:00Z")

    def test_timezone_conversion(self):
        """Test that timezone conversion from local to UTC works correctly."""
        # Simulate LA observation at 8:28 AM PDT (should become 15:28 UTC)
        data = {
            "current_condition": [{
                "localObsDateTime": "2025-10-28 08:28 AM"
            }]
        }
        city_info = {"city": "Los Angeles", "country": "USA", "tz": "America/Los_Angeles"}

        wttr = Wttr("http://wttr.in/{city},{country}?format=j2")
        result = wttr.parse_observation_time(data, city_info)

        self.assertIsNotNone(result)
        # Verify it's a datetime object
        self.assertIsInstance(result, datetime)
        # Verify it's a naive datetime (no timezone info - represents UTC)
        self.assertIsNone(result.tzinfo)
        # Verify the time is correct (8:28 AM PDT = 15:28 UTC during DST)
        # Note: This test assumes DST is active on 2025-10-28
        self.assertEqual(result.hour, 15)
        self.assertEqual(result.minute, 28)

    @patch('requests.get')
    def test_wttr_fetch_data(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "current_condition": [{"temp_C": "20"}],
            "nearest_area": [{"areaName": [{"value": "TestCity"}]}]
        }
        wttr = Wttr("http://wttr.in/{city},{country}?format=j1")
        city_info = {"city": "TestCity", "country": "TestCountry"}
        data = wttr.fetch_data(city_info)

        self.assertIsNotNone(data)
        mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()