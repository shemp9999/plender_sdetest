import logging
import requests
import time

class Wttr:

    def __init__(self, api_url_template):
        self.api_url_template = api_url_template

    def fetch_data(self, location_info):
        """Fetch weather report for a city."""
        city = location_info.get("city")
        country = location_info.get("country")

        # Replace spaces with + for wttr.in (works better than %20 encoding)
        city_formatted = city.replace(' ', '+')
        api_url = self.api_url_template.format(city=city_formatted, country=country)

        start = time.time()
        
        try:
            response = requests.get(api_url, timeout=10)
            duration = time.time() - start

            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Check if it's actually an error disguised as 200 OK
                    # wttr.in returns "Unknown location" when at capacity
                    nearest_area = data.get("nearest_area", [{}])[0]
                    if not nearest_area or nearest_area.get("areaName", [{}])[0].get("value") == "":
                        logging.error(f"WTTR     : Service at capacity for {city} (returned empty location) - {api_url}")
                        return None
                    
                    # Also check for the "Unknown location" message
                    current_condition = data.get("current_condition", [])
                    if not current_condition:
                        logging.error(f"WTTR     : Service at capacity for {city} (no weather data) - {api_url}")
                        return None
                    
                    logging.debug(f"WTTR     : Fetched {city} in {duration:.2f}s")
                    return data
                    
                except (KeyError, IndexError, ValueError) as e:
                    logging.error(f"WTTR     : Invalid response for {city} - {str(e)}")
                    return None
            
            elif response.status_code == 404:
                # wttr.in bug: 404s sometimes return weather data for wrong city
                # https://github.com/chubin/wttr.in/issues/500
                if len(response.content) > 1000:
                    try:
                        data = response.json()
                        returned_city = data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", "")
                        if returned_city and returned_city.lower() != city.lower():
                            logging.warning(f"WTTR     : 404 for '{city}' - API returned '{returned_city}' instead - {api_url}")
                        else:
                            logging.error(f"WTTR     : Failed [HTTP 404] {city} - {api_url}")
                    except (KeyError, IndexError, ValueError):
                        logging.error(f"WTTR     : Failed [HTTP 404] {city} - {api_url}")
                else:
                    logging.error(f"WTTR     : Failed [HTTP 404] {city} - {api_url}")
                return None
            
            else:
                logging.error(f"WTTR     : Failed [HTTP {response.status_code}] {city} - {api_url}")
                return None

        except requests.exceptions.Timeout:
            duration = time.time() - start
            logging.error(f"WTTR     : Timeout for {city} after {duration:.1f}s - {api_url}")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"WTTR     : Connection failed for {city} - {str(e)[:80]}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"WTTR     : Request failed for {city} - {str(e)[:80]}")
            return None