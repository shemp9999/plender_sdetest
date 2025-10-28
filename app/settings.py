# Cities to monitor for weather data
# Note: Using 3-letter ISO country codes (USA, MEX, CRI)
# Timezone: IANA timezone identifier for converting localObsDateTime to UTC
#
# LIMITATION: Timezones are statically configured per city.
# Use geonames API (http://api.geonames.org/timezoneJSON)
# (determine timezone from lat/long coordinates)
CITY_DICTS = [
    {"city": "Savannah", "country": "USA", "tz": "America/New_York"},
    {"city": "Los Angeles", "country": "USA", "tz": "America/Los_Angeles"},
    {"city": "Los Gatos", "country": "USA", "tz": "America/Los_Angeles"},
    {"city": "Olympia", "country": "USA", "tz": "America/Los_Angeles"},
    {"city": "Mulege", "country": "MEX", "tz": "America/Mazatlan"},
    {"city": "Philadelphia", "country": "USA", "tz": "America/New_York"},
    {"city": "Boulder", "country": "USA", "tz": "America/Denver"},
    {"city": "San Diego", "country": "USA", "tz": "America/Los_Angeles"},
    {"city": "San Francisco", "country": "USA", "tz": "America/Los_Angeles"},
    {"city": "Tamarindo", "country": "CRI", "tz": "America/Costa_Rica"}
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