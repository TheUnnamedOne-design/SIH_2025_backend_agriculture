import requests
from requests.exceptions import Timeout, ConnectionError, RequestException
import time

class APIService:
    def __init__(self, ogd_api_key: str, resource_id: str):
        self.ogd_api_key = ogd_api_key
        self.resource_id = resource_id
        self.base_url = "https://api.data.gov.in/resource"

    def get_soil_moisture(self, district_name):
        """Original method - kept for compatibility"""
        url = f"{self.base_url}/{self.resource_id}"
        params = {
            "api-key": self.ogd_api_key,
            "format": "json",
            "limit": 10,
            "filters[districtname]": district_name.upper()
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])
        except (Timeout, ConnectionError, RequestException) as e:
            print(f"API error in get_soil_moisture: {e}")
            return []

    def get_data(self, filters=None, limit=10):
        """New method with timeout handling"""
        url = f"{self.base_url}/{self.resource_id}"
        params = {
            'api-key': self.ogd_api_key,
            'format': 'json',
            'limit': limit
        }
        
        if filters:
            for key, value in filters.items():
                params[f'filters[{key}]'] = value.upper()  # API expects uppercase
        
        print(f"API Request: {url}")
        print(f"Parameters: {params}")
        
        try:
            # Make request with 10-second timeout
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                print(f"API Success: Retrieved {len(records)} records")
                return records
            else:
                print(f"API Error: Status {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return []
                
        except Timeout:
            print("API Request TIMEOUT - Government server is slow/unresponsive")
            return []
            
        except ConnectionError:
            print("API Connection ERROR - Cannot reach government server")
            return []
            
        except RequestException as e:
            print(f"API Request ERROR: {str(e)}")
            return []
            
        except ValueError as e:
            print(f"API JSON Parse ERROR: {str(e)}")
            return []
            
        except Exception as e:
            print(f"Unexpected API ERROR: {str(e)}")
            return []

    def get_data_with_retry(self, filters=None, limit=10, max_retries=2):
        """Get data with retry logic - THIS WAS MISSING"""
        for attempt in range(max_retries + 1):
            try:
                print(f"API Attempt {attempt + 1}/{max_retries + 1}")
                
                url = f"{self.base_url}/{self.resource_id}"
                params = {
                    'api-key': self.ogd_api_key,
                    'format': 'json',
                    'limit': limit
                }
                
                if filters:
                    for key, value in filters.items():
                        params[f'filters[{key}]'] = value.upper()
                
                # Shorter timeout for retries
                timeout = 5 if attempt > 0 else 10
                response = requests.get(url, params=params, timeout=timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    records = data.get('records', [])
                    print(f"API Success on attempt {attempt + 1}: {len(records)} records")
                    return records
                else:
                    print(f"API returned status {response.status_code} on attempt {attempt + 1}")
                    
            except (Timeout, ConnectionError, RequestException) as e:
                print(f"Attempt {attempt + 1} failed: {e.__class__.__name__}")
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print("All retry attempts failed - using fallback")
                    
            except Exception as e:
                print(f"Unexpected error on attempt {attempt + 1}: {e}")
                break  # Don't retry on unexpected errors
        
        return []  # Return empty list if all attempts fail
