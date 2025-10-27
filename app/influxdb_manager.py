from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, WriteOptions
import logging

class InfluxDBClientManager:
    """Manages InfluxDB client connection and operations."""

    def __init__(self, url, token, org, bucket):
        """Set up InfluxDB connection."""
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket

        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=WriteOptions(write_type=SYNCHRONOUS))

    def bucket_exists(self):
        try:
            buckets_api = self.client.buckets_api()
            buckets = buckets_api.find_buckets().buckets
            
            exists = any(bucket.name == self.bucket for bucket in buckets)
            return exists
        except Exception as e:
            logging.error(f"INFLUXDB : Failed to check bucket: {e}")
            return False

    def create_bucket(self):
        try:
            buckets_api = self.client.buckets_api()
            buckets_api.create_bucket(bucket_name=self.bucket, org=self.org)
            logging.info(f"INFLUXDB : Bucket '{self.bucket}' created.")
            return True
        except Exception as e:
            logging.error(f"INFLUXDB : Failed to create bucket: {e}")
            return False

    def data_exists(self, city, timestamp):
        """Check if current weather report exists (we skip duplicates)."""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "weather_data")
          |> filter(fn: (r) => r.city == "{city}")
          |> filter(fn: (r) => r._time == time(v: "{timestamp}"))
          |> limit(n: 1)
        '''
        result = self.client.query_api().query(org=self.org, query=query)

        exists = len(result) > 0
        return exists

    def write_data(self, point):
        """Write data to InfluxDB."""
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            return True
        except Exception as e:
            logging.error(f"INFLUXDB : Write failed: {e}")
            return False

    def close(self):
        """Close connection."""
        self.client.close()