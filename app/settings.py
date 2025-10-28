# Cities to monitor for weather data
# Note: Using 3-letter ISO country codes (USA, MEX, CRI)
CITY_DICTS = [
    {"city": "Savannah", "country": "USA"},
    {"city": "Los Angeles", "country": "USA"},
    {"city": "Los Gatos", "country": "USA"},
    {"city": "Olympia", "country": "USA"},
    {"city": "Mulege", "country": "MEX"},
    {"city": "Philadelphia", "country": "USA"},
    {"city": "Boulder", "country": "USA"},
    {"city": "San Diego", "country": "USA"},
    {"city": "San Francisco", "country": "USA"},
    {"city": "Tamarindo", "country": "CRI"}
]

# Field mappings: field name -> wttr.in JSON key
MEASUREMENTS = {
    "humidity": "humidity",
    "pressure": "pressureInches",
    "temp_celsius": "temp_C",
    "temp_fahrenheit": "temp_F",
    "temp_kelvin": "temp_K",
    "cloudcover": "cloudcover",
    "latitude": "latitude",
    "longitude": "longitude",
}

# Kelvin equivalent of zero degrees Celsius (zero sig figs)
KELVIN_OFFSET = 273

# wttr.in API configuration
# j2 format excludes hourly forecasts (92% reduction in payload size: 50KB -> 4KB)
WTTR_URL_TEMPLATE = "http://wttr.in/{city},{country}?format=j2"

# InfluxDB configuration
INFLUXDB_CONFIG = "/usr/src/influxdb2_config/influx-configs"
INFLUXDB_URL = "http://influxdb2:8086"
BUCKET_NAME = "weather_data"