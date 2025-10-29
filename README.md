# Weather Data Collection System

A Python app that polls weather data from wttr.in every 30 seconds and stores it in InfluxDB.

**Assessment:** This project was built for the [cCAS SDE Take-Home Assessment](cCAS%20SDE%20Take-Home%20Assessment.md).

**For development process and design decisions, see [PROJECT-REVIEW.md](PROJECT-REVIEW.md)**

## Overview

Gets weather for 10 cities every 30 seconds and writes to InfluxDB. Logs new observations and handles API failures.

## Architecture

- **Python 3-slim** - Application runtime (minimal image for faster startup)
- **InfluxDB Client** - Data storage interface
- **wttr.in API** - Weather data source
- **Docker Compose** - Container orchestration

### Components

- `app/main.py` - Application orchestration and data processing
- `app/influxdb_manager.py` - InfluxDB client wrapper with error handling
- `app/wttr_manager.py` - Weather API client with timeout handling
- `app/settings.py` - Configuration constants (cities, measurements, endpoints)
- `app/tests.py` - Unit tests with mocking

## What You Need

- Docker and Docker Compose
- That's it (dependencies are in the container)

## Quick Start

### 1. Start the Application

```bash
docker compose up
```

This will:

- Start InfluxDB container
- Build and start the Python application container
- Begin polling weather data every 30 seconds

### 2. Check It's Working

Watch the logs:

```bash
docker compose logs -f sdetest
# OR using container name:
docker logs -f plender_sdetest
```

You should see something like:

```text
INFO - INFLUXDB : Configuration file '/usr/src/influxdb2_config/influx-configs' loaded.
INFO -          : Cities: 10/10 | Fetch:    482.4ms | Transform:    1.8ms | Record:   17.4ms | Total:    506.4ms ( 1.7%) | Recorded: Savannah, Los Angeles, Los Gatos, Olympia, Mulege, Philadelphia, Boulder, San Diego, San Francisco, Tamarindo
INFO -          : Cities: 10/10 | Fetch:    352.5ms | Transform:    1.0ms | Record:   25.9ms | Total:    393.2ms ( 1.3%)
INFO -          : Cities: 10/10 | Fetch:    734.3ms | Transform:    0.8ms | Record:   25.0ms | Total:    782.9ms ( 2.6%) | Recorded: Boulder
```

The status line shows:
- **Cities: 10/10** - Successful fetches out of total (will show 8/10 if 2 cities timeout)
- **Fetch** - Time to fetch all cities in parallel (milliseconds)
- **Transform** - Time to parse and build InfluxDB points (milliseconds)
- **Record** - Time to write all points to InfluxDB (milliseconds)
- **Total** - Complete cycle time with budget percentage (% of 30s cycle used)
- **Recorded** - Which cities had new observation timestamps (only shown when new data is recorded)

If there are failures, you'll see error logs before the status line:

```text
ERROR - WTTR     : Timeout for Tamarindo after 10.0s - http://wttr.in/Tamarindo,CRI?format=j2
INFO -          : Cities: 9/10 | Fetch:  10153.2ms | Transform:    0.8ms | Record:   24.1ms | Total:  10195.6ms (34.0%)
```

### 3. Access InfluxDB

InfluxDB UI is available at: http://localhost:8086

**Login credentials are set in docker-compose.yml:**

- Check the `DOCKER_INFLUXDB_INIT_USERNAME` and `DOCKER_INFLUXDB_INIT_PASSWORD` environment variables
- Default organization: `nflx`
- Data bucket: `weather_data`

### 4. Stop the Application

```bash
docker compose down
```

To remove data volumes:

```bash
docker compose down -v
```

## Data Collection

### Cities Monitored

- **USA (8 cities):** Savannah, Los Angeles, Los Gatos, Olympia, Philadelphia, Boulder, San Diego, San Francisco
- **Mexico (1 city):** Mulege
- **Costa Rica (1 city):** Tamarindo

### Measurements Collected

**Fields (numeric measurements):**

- Humidity
- Pressure (inches)
- Temperature (Celsius, Fahrenheit, Kelvin)
- Cloud cover
- Latitude and Longitude

**Tags (indexed metadata):**

- City
- Country (3-letter ISO code: USA, MEX, CRI)

### Collection Frequency

- **Polling interval:** 30 seconds (work typically uses 1-3% of cycle, 97-99% sleeping)
- **Parallel fetching:** 10 concurrent requests
- **Timeout:** 10 seconds per request
- **Status logging:** Single-line summary shows timing breakdown (Fetch/Transform/Record/Total) and budget percentage
- **Recording:** City names appear in "Recorded:" list when wttr.in returns a new observation timestamp

## Configuration

Configuration is stored in `app/settings.py`:

- `CITY_DICTS` - List of cities to monitor with:
  - `city` - City name (e.g., "Los Angeles")
  - `country` - 3-letter ISO country code (e.g., "USA", "MEX", "CRI")
  - `tz` - IANA timezone identifier (e.g., "America/Los_Angeles") for converting local observation times to UTC
- `MEASUREMENTS` - 8 numeric fields to collect and store
- `KELVIN_OFFSET` - Constant for Celsius to Kelvin conversion (273, matches whole-number precision from API)
- `WTTR_URL_TEMPLATE` - Weather API endpoint (using j2 format)
- `INFLUXDB_URL` - InfluxDB connection string
- `BUCKET_NAME` - InfluxDB bucket for time-series data

## Querying Data

You can query the data from InfluxDB using Flux queries.

### Example: Get All Weather Data

```flux
from(bucket: "weather_data")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "weather_data")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["city", "_time"])
```

### Example: Get Latest Data for a City

```flux
from(bucket: "weather_data")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "weather_data")
  |> filter(fn: (r) => r.city == "Savannah")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
```

You can run these queries in the InfluxDB UI at http://localhost:8086 or via the CLI.

## Testing

Run unit tests:

```bash
cd app
../.venv/bin/python -m unittest tests.py
```

Or using Docker:

```bash
docker compose run sdetest python -m unittest tests.py
```

Tests cover:

- Timestamp tracking logic (new vs duplicate timestamps)
- Data write operations with logging behavior
- API error handling (timeouts, HTTP failures)

## Error Handling

The app handles various failure modes from the wttr.in API:

**API Failures:**

- **Timeouts (10s):** Logs error with actual duration, skips city, continues
- **Connection errors:** Logs error, continues with other cities
- **HTTP 404 errors:** Detects wttr.in bug (wrong city data), logs warning
- **HTTP 200 with invalid data:** Service at capacity, validates response

**Data Issues:**

- **Invalid timestamps:** Logs error, skips city
- **Missing measurements:** Logs warning, writes partial data

**InfluxDB Issues:**

- **Write failures:** Logs error, retries next cycle
- **Missing bucket:** Creates bucket on startup
- **Duplicate data:** Queries before writing to prevent duplicates

**Batch Failures:**

When wttr.in service is completely down, all cities timeout and no data is written. The application logs the total failure count and retries on the next 30-second cycle.

All errors are logged with context (city name, URL, error type) for debugging.

## Design Choices

### Duplicate Detection

Queries InfluxDB before writing to check if a point with the same city and timestamp already exists. Uses Flux query with proper time comparison: `r._time == time(v: "timestamp")`. Prevents recording duplicate data.

### Synchronous Write Mode

Synchronous writes for thread safety. Data integrity over speed.

### Parallel Fetching

Fetches 10 cities in parallel with ThreadPoolExecutor.

### API Format Optimization

Uses wttr.in's `j2` format instead of `j1` - 92% smaller payload (50KB → 4KB).

### Timestamp Parsing

wttr.in returns times in each city's local timezone. We convert to UTC using Python's built-in `zoneinfo` before storing in InfluxDB.

Without conversion: LA at 8:28 AM would be stored as 8:28 AM UTC (wrong - should be 3:28 PM UTC).

Uses static timezone mapping in settings.py. For hundreds of cities, could use geonames API to look up timezones programmatically.

## Troubleshooting

### Container Fails to Start

**Issue:** Python app crashes immediately

**Solution:** InfluxDB config file might not be ready yet. The app waits up to 120 seconds for it. Check logs:

```bash
docker compose logs influxdb2
```

### No Data Written

**Issue:** API timeouts or network errors

**Solution:** Check wttr.in API status. The app retries every 30 seconds. Look for:

```text
   ERROR - WTTR     :  Timeout for [city] after 10.0s - [spi_url]
```

### Duplicate Data

**Issue:** Data appears multiple times for same timestamp

**Solution:** This should not happen due to duplicate detection. When duplicates are detected, the app silently skips writing them. Check if data is actually being written:

```bash
docker compose logs sdetest | grep "Recorded"
# Each new write shows: "INFLUXDB : Recorded [city] weather report ([timestamp])."
# If you restart the app and see no "Recorded" messages, duplicates are being skipped correctly.
```

If duplicates persist in InfluxDB queries, the wttr.in API may be returning stale observation times or the duplicate detection query may need adjustment.

### wttr.in Service Issues

**Issue:** Multiple cities timing out simultaneously

**Cause:** wttr.in service is overloaded or down

**Solution:** This is expected behavior. The app will:

1. Log timeout errors for affected cities
2. Continue collecting data for cities that respond
3. Automatically retry all cities on next cycle (30 seconds)

Check logs for patterns:

```bash
docker compose logs sdetest | grep "Fetched"
# Look for: "Fetched X/10 weather reports"
# 0/10 = service completely down
# 8-10/10 = normal operation with occasional failures
# 1-7/10 = service degraded
```

**Issue:** HTTP 404 with "returned wrong city" warning

**Cause:** wttr.in bug (<https://github.com/chubin/wttr.in/issues/500>)

**Solution:** Should be rare with current encoding. If frequent, verify city names in settings.py use `+` for spaces and 3-letter country codes (USA, MEX, CRI).

## Project Structure

```text
.
├── app/
│   ├── main.py              # Application entry point
│   ├── influxdb_manager.py  # InfluxDB operations
│   ├── wttr_manager.py      # Weather API client
│   ├── settings.py          # Configuration
│   ├── tests.py             # Unit tests
│   └── requirements.txt     # Python dependencies
├── docker-compose.yml       # Service orchestration
├── Dockerfile               # Python app container
├── README.md                # This file
└── PROJECT-REVIEW.md        # Development process and design decisions
```

## Dependencies

Python packages (see `app/requirements.txt`):

- `influxdb-client` - InfluxDB 2.x client library
- `requests` - HTTP client for wttr.in API

## Adding Cities

Edit `app/settings.py` and add the city with its timezone:

```python
CITY_DICTS = [
    {"city": "Your City", "country": "USA", "tz": "America/New_York"},
    # ... existing cities
]
```

Use IANA timezone identifiers like "America/Los_Angeles" or "Europe/London". Find them at <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>.

Restart the application:

```bash
docker compose restart sdetest
```
