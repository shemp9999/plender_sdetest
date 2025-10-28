import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import configparser
import settings

from influxdb_client import Point, WritePrecision
from influxdb_manager import InfluxDBClientManager
from wttr_manager import Wttr

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)8s - %(message)s')

def _load_config(file_path):
    """Load InfluxDB config from file."""
    config = configparser.ConfigParser()
    config.read(file_path)
    logging.info(f"INFLUXDB : Configuration file '{file_path}' loaded.")
    return config

def wait_for_config(file_path, check_interval=5, max_wait=120):
    """Wait for InfluxDB container to provide config file."""
    elapsed = 0
    while not os.path.exists(file_path):
        if elapsed >= max_wait:
            logging.error(f"INFLUXDB : Timeout waiting for config file")
            raise TimeoutError(f"Configuration file '{file_path}' not found")
        time.sleep(check_interval)
        elapsed += check_interval

def _get_field_value(field_name, json_key, current_condition, nearest_area):
    """Get field from API response with special cases for lat/long and Kelvin."""
    if field_name in ["latitude", "longitude"]:
        return nearest_area.get(json_key)
    elif field_name == "temp_kelvin":
        temp_c = current_condition.get("temp_C", 0)
        try:
            return float(temp_c) + settings.KELVIN_OFFSET
        except (ValueError, TypeError) as e:
            logging.error(f"WTTR     : Invalid temp_C for Kelvin: {temp_c} - {e}")
            return None
    else:
        return current_condition.get(json_key)

def _write_point(influx_manager, point, city, timestamp, missing_fields):
    """Write weather report to InfluxDB (skip if exists)."""
    if influx_manager.data_exists(city, timestamp):
        return False

    if influx_manager.write_data(point):
        logging.info(f"INFLUXDB : Recorded {city} weather report ({timestamp}).")
        if missing_fields:
            logging.warning(f"INFLUXDB : Missing fields for {city}: {', '.join(missing_fields)}")
        return True

    return False
    
def _build_point(data, city_info, measurements, wttr):
    """Transform weather report for InfluxDB."""
    city = city_info["city"]
    country = city_info["country"]
    current_condition = data.get("current_condition", [{}])[0]
    nearest_area = data.get("nearest_area", [{}])[0]

    # Parse observation timestamp
    timestamp = wttr.parse_observation_time(data, city_info)
    if timestamp is None:
        return (None, [], city, None)

    point = Point("weather_data") \
        .tag("city", city) \
        .tag("country", country) \
        .time(timestamp, WritePrecision.NS)

    missing_fields = []

    for field_name, json_key in measurements.items():
        value = _get_field_value(field_name, json_key, current_condition, nearest_area)

        if value is not None:
            try:
                value = float(value)
                point.field(field_name, value)
            except (ValueError, TypeError) as e:
                logging.error(f"WTTR     : Invalid numeric value for '{field_name}' in {city}: {value} - {e}")
                missing_fields.append(field_name)
        else:
            logging.warning(f"WTTR     : Measurement '{field_name}' not found for {city}.")
            missing_fields.append(field_name)

    return (point, missing_fields, city, timestamp)

def _fetch_and_process_weather_data(wttr, influx_manager):
    """Fetch weather reports and write to InfluxDB."""
    fetch_start = time.time()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(wttr.fetch_data, settings.CITY_DICTS))
    
    fetch_duration = time.time() - fetch_start
    successful_fetches = sum(1 for r in results if r is not None)
    logging.info(f"WTTR     : Fetched {successful_fetches}/{len(settings.CITY_DICTS)} weather report[s] in {fetch_duration:.2f} seconds.")

    writes = 0
    attempts = 0
    for city_info, data in zip(settings.CITY_DICTS, results):
        if data:
            point, missing_fields, city, timestamp = _build_point(data, city_info, settings.MEASUREMENTS, wttr)
            if point is not None:
                attempts += 1
                if _write_point(influx_manager, point, city, timestamp, missing_fields):
                    writes += 1

def _collect_weather_data(config):
    """Set up managers and run weather report collection cycle."""
    start_time = time.time()

    influx_manager = InfluxDBClientManager(
        url=settings.INFLUXDB_URL,
        token=config['default']['token'].strip('"\''),
        org=config['default']['org'].strip('"\''),
        bucket=settings.BUCKET_NAME
    )

    if not influx_manager.bucket_exists():
        if not influx_manager.create_bucket():
            return

    wttr = Wttr(settings.WTTR_URL_TEMPLATE)

    _fetch_and_process_weather_data(wttr, influx_manager)

    influx_manager.close()

    duration = time.time() - start_time
    logging.info(f"MAIN     : Completed weather report processing in {duration:.2f} seconds.")

def main():
    config_path = settings.INFLUXDB_CONFIG
    wait_for_config(config_path)
    config = _load_config(config_path)

    while True:
        _collect_weather_data(config)
        time.sleep(30)

if __name__ == "__main__":
    main()

