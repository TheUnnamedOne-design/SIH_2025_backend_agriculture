import requests
from geopy.geocoders import Nominatim

class LocationService:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="agricultural-ai-assistant")

    def get_coordinates(self, district_name, state):
        """Get coordinates for a district and state"""
        location = self.geolocator.geocode(f"{district_name}, {state}, India")
        if location:
            return location.latitude, location.longitude
        return None, None

    def get_elevation(self, lat, lon):
        """Get elevation for given coordinates"""
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json().get('results')
            if results:
                elevation = results[0].get('elevation')
                return elevation
        return None
