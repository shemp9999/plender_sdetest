import unittest
from unittest.mock import MagicMock, patch

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
        city_info = {"city": "TestCity", "country": "TestCountry"}
        measurements = {
            "temp_celsius": "temp_C",
            "temp_kelvin": "temp_K",
            "humidity": "humidity",
            "pressure": "pressureInches"
        }

        point, missing_fields, city, timestamp = _build_point(data, city_info, measurements)

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
        city_info = {"city": "TestCity", "country": "TestCountry"}
        measurements = {"temp_celsius": "temp_C"}

        point, missing_fields, city, timestamp = _build_point(data, city_info, measurements)

        self.assertIsNone(point)
        self.assertEqual(city, "TestCity")
        self.assertIsNone(timestamp)
        self.assertEqual(len(missing_fields), 0)

    @patch('influxdb_manager.InfluxDBClientManager')
    def test_write_point_data_exists(self, MockInfluxDBClientManager):
        mock_manager = MockInfluxDBClientManager()
        mock_manager.data_exists.return_value = True  # Data exists

        from influxdb_client import Point
        point = Point("weather_data").tag("city", "TestCity").field("temp", 20.0)

        result = _write_point(mock_manager, point, "TestCity", "2025-04-21T11:55:00Z", [])

        mock_manager.write_data.assert_not_called()
        self.assertFalse(result)

    @patch('influxdb_manager.InfluxDBClientManager')
    def test_write_point_success(self, MockInfluxDBClientManager):
        mock_manager = MockInfluxDBClientManager()
        mock_manager.data_exists.return_value = False
        mock_manager.write_data.return_value = True

        from influxdb_client import Point
        point = Point("weather_data").tag("city", "TestCity").field("temp", 20.0)

        result = _write_point(mock_manager, point, "TestCity", "2025-04-21T11:55:00Z", [])

        mock_manager.write_data.assert_called_once()
        self.assertTrue(result)

    @patch('requests.get')
    def test_wttr_fetch_data(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"current_condition": [{"temp_C": "20"}]}
        wttr = Wttr("http://wttr.in/{city},{country}?format=j1")
        city_info = {"city": "TestCity", "country": "TestCountry"}
        data = wttr.fetch_data(city_info)

        self.assertIsNotNone(data)
        mock_get.assert_called_once()

if __name__ == '__main__':
    unittest.main()