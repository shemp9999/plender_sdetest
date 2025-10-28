# Project Review: Weather Data Collection System

**Assessment Context:** Built for the [cCAS SDE Take-Home Assessment](cCAS%20SDE%20Take-Home%20Assessment.md).

This review documents the iterative development process, showing problem-solving, technical decision-making, and production engineering practices. The app evolved through multiple refinements, each addressing real issues discovered during development and testing.

## What Was Asked For

- Fetch weather data from wttr.in every 30 seconds
- Collect data for ten cities across at least two countries
- Store 8 measurements in InfluxDB: humidity, pressure, temperature (C/F/K), cloud cover, latitude, longitude
- Run in Docker containers
- Handle InfluxDB authentication
- Include logging and tests
- Consider scalability and concurrency (bonus)

## What Got Built

- Polls wttr.in every 30 seconds
- Ten cities: Savannah, Los Angeles, Los Gatos, Olympia, Philadelphia, Boulder, San Diego, San Francisco (US), Mulege (Mexico), Tamarindo (Costa Rica)
- Stores all 8 measurements in InfluxDB time-series format (humidity, pressure, temps in C/F/K, cloudcover, lat/long)
- Runs in Docker with single `docker compose up` command
- Authenticates to InfluxDB using token from auto-generated config file with 120-second wait timeout
- Includes logging at all stages (startup, fetching, writing, errors)
- Includes unit tests with mocks for API and database operations
- Fetches cities in parallel using ThreadPoolExecutor (10 workers)
- Queries for duplicates before writing (removed - see Duplicate Detection Evolution)
- Handles API failures, timeouts, missing data without crashing

---

## Build Issues and Solutions

### Async InfluxDB Writes Failing

Async writes crashed with connection errors. Switched to synchronous mode. Understood this went against the bonus question about concurrency. At the time, reads from wttr were taking 10 seconds per cycle. Later optimized to 1-3 seconds with parallelization. With 30-second cycles and optimized fetching, system has 93% idle time. Documented as technical debt for future refactoring.

### Container Startup and Config Timing

Python app tried reading InfluxDB config immediately. File takes 5-15 seconds to appear after container start. Added wait loop with 120-second timeout:

```python
def wait_for_config(file_path, check_interval=5, max_wait=120):
    elapsed = 0
    while not os.path.exists(file_path):
        if elapsed >= max_wait:
            raise TimeoutError(f"Config file not found")
        time.sleep(check_interval)
        elapsed += check_interval
```

App waits but fails fast if something's broken.

Also addressed container size. Started with `python:latest` - 900MB, 30+ second startup. Switched to `python:3-slim` - 150MB, 5-15 second startup. Same functionality, much faster. Left wait code for reliability across environments.

### Duplicate Logging

Every log message appeared twice. Found `logging.basicConfig()` in two files. Removed duplicate. Still duplicated. Different cause - Dockerfile had `COPY app/` and docker-compose had volume mount. Code existed in two places. Removed COPY, kept volume mount.

### Token Format

InfluxDB config wraps values in quotes. Python reads quotes literally. InfluxDB rejects quoted tokens. Stripped quotes:

```python
token = config['default']['token'].strip('"\'')
```

### Data Model

Initially wrote 10 separate records per city (one per field). 100 database writes every 30 seconds. Learned InfluxDB expects complete snapshots - all fields together. Refactored to one Point with all 8 fields:

```python
point = Point("weather_data") \
    .tag("city", "Savannah") \
    .tag("country", "US") \
    .time(timestamp) \
    .field("humidity", 74.0) \
    .field("pressure", 30.0) \
    .field("temp_celsius", 18.0) \
    .field("temp_fahrenheit", 64.4) \
    .field("temp_kelvin", 291.0) \
    # ... all other fields
```

Result: 90% fewer writes, atomic updates. Changed field names to snake_case convention. Removed redundant City/Country fields (already in tags).

### Kelvin Calculation

Requirements specified Celsius, Fahrenheit, Kelvin. API provides C and F only. Calculated Kelvin as `temp_c + 273`. Used 273 instead of 273.15 because wttr.in rounds to whole numbers. Using 273.15 implies false precision.

### Bandwidth Usage

Noticed wttr.in offers two formats: j1 (50KB with forecasts) and j2 (4KB current only). Was using j1. Only needed current conditions. Changed to j2. Result: 92% bandwidth reduction, 485 GB/year saved.

### URL Encoding

San Francisco, Los Angeles, San Diego returned 404s. Known wttr.in bug. replaced `%20` space encoding with `+` encoding. Changed from 2-letter to 3-letter country codes. Added detection for wrong city responses. After these changes 404s stopped.

### API Reliability Issues

wttr.in has multiple failure modes. Returns 200 OK when at capacity with empty data. Variable response times (0.7s - 10s+). Connection timeouts. Service sometimes unreachable.

Added comprehensive error detection:

```python
try:
    response = requests.get(api_url, timeout=10)
    if response.status_code == 200:
        # Validate response isn't "service at capacity"
        if not nearest_area or nearest_area.get("areaName")[0].get("value") == "":
            logging.error(f"Service at capacity for {city}")
            return None
except requests.exceptions.Timeout:
    logging.error(f"Timeout for {city} after {duration:.1f}s")
except requests.exceptions.ConnectionError:
    logging.error(f"Connection failed for {city}")
```

Handles Timeout, ConnectionError, RequestException separately. Validates 200 OK responses for empty location or missing weather data. Logs duration for performance tracking. Returns None on failure, allows other cities to continue.

### Sequential Fetching

Fetching 10 cities sequentially took 10-20 seconds. Added ThreadPoolExecutor for parallel requests:

```python
with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(wttr.fetch_data, settings.CITY_DICTS))
```

Result: 10 cities in ~1-3 seconds. Total cycle: 2-4 seconds work, 26-28 seconds idle. Could handle 150+ cities without changes.

### Log Formatting

Mix of uppercase/lowercase, inconsistent spacing. Standardized to 8-character uppercase prefixes:

```text
INFO - WTTR     : Fetched data...
INFO - INFLUXDB : Data written...
INFO - MAIN     : Cycle completed...
```

39 edits across 3 files.

### Timestamp Parsing

Treated `localObsDateTime` as UTC. Wrong. It's local time. Los Angeles 8:28 AM stored as 8:28 AM UTC (actually 3:28 PM UTC). Bad timestamps.

Tried manual timezone calculations. Messy. Date-crossing edge cases got complicated. Tried timezonefinder library - needs gcc for compilation. Failed in python:3-slim.

Added timezone field to each city in settings. Used Python's built-in `zoneinfo` to convert local to UTC. Works. No external dependencies.

Trade-off: manual config doesn't scale to hundreds of cities. For 10 cities, fine. Documented geonames API approach in comments for future scaling.

### Duplicate Detection Evolution

Original implementation queried InfluxDB before writing to check if timestamp already existed. Flux query checked for existing measurement+city+timestamp combination.

Problem: During runtime, queries became unreliable. Returned false negatives - claimed data didn't exist when it did. Suspected InfluxDB indexing delays. Result: noisy logs showing "Recorded" for every city every cycle, even with same timestamp.

Realized InfluxDB handles duplicates via upsert. Writing same measurement+tags+timestamp overwrites previous point. Don't need to prevent writes.

First iteration: Removed data_exists() query entirely. Simpler code, no query overhead, data integrity maintained. Problem: logs still noisy.

Second iteration: Added in-memory timestamp tracking. Dictionary maps city → last_seen_timestamp. Only log "Recorded" for new timestamps. Duplicate timestamps still written (InfluxDB deduplicates) but logged at DEBUG level.

About 15 lines of code. Dictionary persists across polling cycles, resets on restart.

Added two tests: one for new timestamps (INFO log), one for duplicates (DEBUG log only).

---

## What Works

- Duplicate detection prevents repeated data on restarts (removed - see Duplicate Detection Evolution)
- Error handling catches network failures, timeouts, bad timestamps
- Data model uses complete snapshots with atomic writes
- Performance has 93% idle time with room to scale 15x
- Docker setup starts with one command and handles async initialization
- Docker health check ensures InfluxDB is ready before app starts

---

## What Needs Work

- wttr.in reliability varies 60-100%, no fallback API or circuit breaker
- Synchronous writes work for this scale, would need async for larger deployments
- No graceful shutdown on SIGTERM
- Observability limited to logs - no metrics endpoint or application health endpoint

---

## Production Additions

First priority:

- Application health endpoint (Docker health check for InfluxDB startup is implemented)
- Graceful shutdown
- Prometheus metrics
- Fallback weather API

Second priority:

- Circuit breaker
- Structured logging
- Async writes
- Proper secrets management

---

## Key Decisions

**Synchronous over async:** 93% idle time meant speed wasn't the bottleneck. Chose stability. Parallelizing wttr requests was a huge improvement, InfluxDB writes all data in sub-second time.

**python:3-slim:** 83% size reduction and faster startup. Same functionality.

**Write-once data model:** 90% fewer operations, atomic writes. InfluxDB best practice.

**j2 format:** 92% bandwidth savings. One line change.

**273 not 273.15:** Matches source data precision (whole numbers).

**ThreadPoolExecutor:** Parallel I/O without async complexity.

---

## Learnings

**Technical:**

- Docker volume mounts replace files from COPY command - using both creates duplicates
- Python logging is global - configure once in main, not in every module
- InfluxDB expects complete snapshots, not fragmented records
- External APIs have quirks (URL encoding, 200 OK disguised errors)
- Small choices compound (image size, API format, write strategy)

**Process:**

- Build working first, optimize later
- Profile before assuming performance
- Document trade-offs when making them
- Same symptom can be different bugs

**Professional:**

- Ship working code, document limitations
- Track technical debt explicitly
- Be honest about unknowns

---

## Performance Improvements

- Bandwidth: 1.44 GB/day → 109 MB/day (-92%)
- Fetch time: 30s → 1.2s (-96%)
- Database operations: 100/cycle → 10/cycle (-90%)

---

## Evolution

Started with async writes crashing and Docker container timing issues. Debugged each problem as it appeared. Fixed duplicate logging twice - same symptom, different root causes. Handled wttr.in API quirks with URL encoding and error detection. Learned InfluxDB wanted complete snapshots, refactored from 100 writes per cycle to 10. Found the j2 format while investigating timestamps, reduced bandwidth by 92%. Added parallel fetching when measurements showed headroom.

Each iteration identified issues, fixed them, and improved performance. Final code works reliably with capacity to scale.
