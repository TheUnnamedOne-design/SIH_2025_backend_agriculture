import os
import json
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform

class SoilService:
    def __init__(self):
        self.albers_crs = CRS.from_proj4(
            '+proj=aea +lat_1=28 +lat_2=12 +lat_0=20 +lon_0=78 +x_0=2000000 +y_0=2000000 +datum=WGS84 +units=m +no_defs'
        )

    def query_asc(self, lat, lon, asc_path):
        with rasterio.open(asc_path) as src:
            src_crs = src.crs or self.albers_crs
            x, y = transform('EPSG:4326', src_crs, [lon], [lat])
            for val in src.sample([(x[0], y[0])]):
                if val[0] == -9999:
                    return None
                return val[0]
        return None

    def read_fraction_folder(self, folder_path, lat, lon, scale=10000):
        values = {}
        for file_name in sorted(os.listdir(folder_path)):
            if file_name.lower().endswith('.asc'):
                asc_file = os.path.join(folder_path, file_name)
                val = self.query_asc(lat, lon, asc_file)
                if val is not None:
                    values[file_name.replace('.asc', '')] = val / scale
                else:
                    values[file_name.replace('.asc', '')] = 'No data'
        return values

    def read_density_file(self, file_path, lat, lon):
        val = self.query_asc(lat, lon, file_path)
        if val is not None:
            return val
        else:
            return 'No data'

    def get_complete_soil_profile(self, base_path, lat, lon):
        profile = {}

        # Carbon density files explicitly
        organic_carbon_file = os.path.join(base_path, 'mean_carbon', 'meantocd.asc')
        inorganic_carbon_file = os.path.join(base_path, 'mean_carbon', 'meanticd.asc')

        profile['Mean Organic Carbon Density (Mg/ha)'] = self.read_density_file(organic_carbon_file, lat, lon)
        profile['Mean Inorganic Carbon Density (Mg/ha)'] = self.read_density_file(inorganic_carbon_file, lat, lon)

        # Soil Depth fractions folder
        soil_depth_folder = os.path.join(base_path, 'soil_depth')
        profile['Soil Depth Fractions'] = self.read_fraction_folder(soil_depth_folder, lat, lon)

        # Soil Type fractions folder
        soil_type_folder = os.path.join(base_path, 'soil_type')
        profile['Soil Type Fractions'] = self.read_fraction_folder(soil_type_folder, lat, lon)

        return profile

    def get_soil_data(self, district_name, base_directory, latitude, longitude, api_service):
        """
        Fetch soil moisture data and complete soil profile for a given district and location.
        Returns a string containing soil information.
        """
        soil_data_str = ""

        # Get soil moisture data
        data = api_service.get_soil_moisture(district_name)
        if not data:
            soil_data_str += "No soil moisture records found.\n"
        else:
            # Just take the first record as a sample
            record = data[0]
            soil_data_str += f"Soil Moisture Data (sample): {json.dumps(record)}\n"

        # Get complete soil profile
        soil_profile = self.get_complete_soil_profile(base_directory, latitude, longitude)
        soil_data_str += f"Complete Soil Profile at location: {latitude}, {longitude}\n"

        for category, values in soil_profile.items():
            soil_data_str += f"\n{category}: "
            if isinstance(values, dict):
                for key, val in values.items():
                    soil_data_str += f"{key[1:]}: {val}, "
            else:
                soil_data_str += f"{values}, "
        return soil_data_str
