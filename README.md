# Weather Data Collection System

A Python app that polls weather data from wttr.in every 30 seconds and stores it in InfluxDB.

**Assessment:** This project was built for the [cCAS SDE Take-Home Assessment](cCAS%20SDE%20Take-Home%20Assessment.md).

**For development process and design decisions, see [PROJECT-REVIEW.md](PROJECT-REVIEW.md)**

## Overview

Gets weather for 10 cities every 30 seconds and writes to InfluxDB. Includes duplicate detection to prevent data corruption and handles API failures.

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
docker compose up --build
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
INFO -          : Beginning weather report processing.
INFO - WTTR     : Fetched 10/10 weather report[s] in 5.24 seconds.
INFO - INFLUXDB : Recorded Los Angeles weather report (2025-10-27T10:46:00Z).
INFO -          : Completed weather report processing in 5.32 seconds.
```

If there are failures, you'll see:

```text
ERROR - WTTR     : Timeout for Tamarindo after 10.0s - http://wttr.in/Tamarindo,CRI?format=j2
INFO - WTTR      : Fetched 9/10 weather report[s] in 10.15 seconds.
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

- **Polling interval:** 30 seconds
- **Parallel fetching:** 10 concurrent requests
- **Timeout:** 10 seconds per request
- **Duplicate detection:** Prevents duplicate writes on restart

## Configuration

Configuration is stored in `app/settings.py`:

- `CITY_DICTS` - List of cities to monitor (with country codes)
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

- Duplicate detection logic
- Data write operations
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

Edit `app/settings.py`:

```python
CITY_DICTS = [
    {"city": "Your City", "country": "US"},
    # ... existing cities
]
```

Restart the application:

```bash
docker compose restart sdetest
```
