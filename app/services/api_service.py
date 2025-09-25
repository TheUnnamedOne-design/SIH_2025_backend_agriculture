import requests

class APIService:
    def __init__(self, ogd_api_key: str, resource_id: str):
        self.ogd_api_key = ogd_api_key
        self.resource_id = resource_id

    def get_soil_moisture(self, district_name):
        url = f"https://api.data.gov.in/resource/{self.resource_id}"
        params = {
            "api-key": self.ogd_api_key,
            "format": "json",
            "limit": 10,
            "filters[districtname]": district_name.upper()
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("records", [])
