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

def _write_point(influx_manager, point, city, timestamp, missing_fields, last_seen):
    """ 
    Write weather report to InfluxDB. 
    Returns city name if new timestamp recorded, None otherwise.
    """
    # Check if this is a new timestamp for this city
    is_new = last_seen.get(city) != timestamp

    if influx_manager.write_data(point):
        if is_new:
            last_seen[city] = timestamp
            if missing_fields:
                logging.warning(f"INFLUXDB : Missing fields for {city}: {', '.join(missing_fields)}")
            return city  # Return city name for summary collection
        else:
            logging.debug(f"INFLUXDB : Re-wrote {city} ({timestamp}) - same timestamp.")

        if missing_fields:
            logging.warning(f"INFLUXDB : Missing fields for {city}: {', '.join(missing_fields)}")
        return None

    return None
    
def _build_point(data, city_info, measurements, wttr):
    """Transform weather report for InfluxDB."""
    city = city_info["city"]
    country = city_info["country"]
    current_condition = data.get("current_condition", [{}])[0]
    nearest_area = data.get("nearest_area", [{}])[0]

    # Parse observation timestamp (returns datetime object)
    timestamp_dt = wttr.parse_observation_time(data, city_info)
    if timestamp_dt is None:
        return (None, [], city, None)

    # Convert to ISO string for InfluxDB (used for both write and query)
    timestamp_str = timestamp_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    point = Point("weather_data") \
        .tag("city", city) \
        .tag("country", country) \
        .time(timestamp_str, WritePrecision.NS)

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

    return (point, missing_fields, city, timestamp_str)

def _fetch_and_process_weather_data(wttr, influx_manager, last_seen_timestamps):
    """
    Fetch weather reports and write to InfluxDB. 
    Returns timing metrics, successful city count, and recorded cities.
    """
    # Fetch phase
    fetch_start = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(wttr.fetch_data, settings.CITY_DICTS))
    fetch_duration = time.time() - fetch_start

    # Transform phase
    transform_start = time.time()
    points_to_write = []
    for city_info, data in zip(settings.CITY_DICTS, results):
        if data:
            point, missing_fields, city, timestamp = _build_point(data, city_info, settings.MEASUREMENTS, wttr)
            if point is not None:
                points_to_write.append((point, city, timestamp, missing_fields))
    transform_duration = time.time() - transform_start

    # Record phase
    record_start = time.time()
    recorded_cities = []
    for point, city, timestamp, missing_fields in points_to_write:
        recorded_city = _write_point(influx_manager, point, city, timestamp, missing_fields, last_seen_timestamps)
        if recorded_city:
            recorded_cities.append(recorded_city)
    record_duration = time.time() - record_start

    return fetch_duration, transform_duration, record_duration, len(points_to_write), recorded_cities

def _collect_weather_data(config, last_seen_timestamps):
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

    fetch_duration, transform_duration, record_duration, successful_cities, recorded_cities = _fetch_and_process_weather_data(
        wttr, influx_manager, last_seen_timestamps
    )

    influx_manager.close()

    # Build summary line
    total_duration = time.time() - start_time
    budget_pct = (total_duration / 30.0) * 100

    # Format with fixed-width fields for alignment: 
    # Cities: 10/10 | Fetch: 340.8ms | Transform:  0.5ms | Record: 23.6ms | Total:  378.7ms (1.3%) | Recorded: [cities]
    summary = f"         : Cities: {successful_cities:2d}/{len(settings.CITY_DICTS)} | "
    summary += f"Fetch: {fetch_duration * 1000:8.1f}ms | "
    summary += f"Transform: {transform_duration * 1000:6.1f}ms | "
    summary += f"Record: {record_duration * 1000:6.1f}ms | "
    summary += f"Total: {total_duration * 1000:8.1f}ms ({budget_pct:4.1f}%)"

    # Add recorded cities if any
    if recorded_cities:
        summary += f" | Recorded: {', '.join(recorded_cities)}"

    logging.info(summary)

def main():
    config_path = settings.INFLUXDB_CONFIG
    wait_for_config(config_path)
    config = _load_config(config_path)

    last_seen_timestamps = {}  # Track last timestamp per city for logging

    while True:
        _collect_weather_data(config, last_seen_timestamps)
        time.sleep(30)

if __name__ == "__main__":
    main()

