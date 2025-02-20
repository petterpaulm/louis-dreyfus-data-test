import xarray as xr
import numpy as np
import os
import logging

from logging_config import logging  # Import logging setup

logging.info("Exporting temperature data to Google Earth KML format...")

# Load dataset
ds = xr.open_dataset("./Outputs/final_dataset.nc")

t2m_celsius = ds["t2m"].isel(step=0) - 273.15
ds = ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180)

# Define KML file path
output_folder = "./Outputs/"
os.makedirs(output_folder, exist_ok=True)
kml_filename = os.path.join(output_folder, "temperature_data.kml")

color_palette = ["#0000FF", "#00FFFF", "#00FF00", "#FFFF00", "#FF7F00", "#FF0000"]
temp_min, temp_max = -30, 50

def get_color(temp):
    norm_temp = np.clip((temp - temp_min) / (temp_max - temp_min), 0, 1)
    index = int(norm_temp * (len(color_palette) - 1))
    return color_palette[index]

# Create KML structure
kml_header = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
"""

kml_body = ""
for lat in ds.latitude.values[::5]:  
    for lon in ds.longitude.values[::5]:
        temp_value = t2m_celsius.sel(latitude=lat, longitude=lon, method="nearest").values
        color = get_color(temp_value)
        kml_body += f"""
<Placemark>
  <name>{temp_value:.1f}°C</name>
  <Point><coordinates>{lon},{lat},0</coordinates></Point>
</Placemark>
"""

kml_footer = """</Document></kml>"""

# Save the KML file
with open(kml_filename, "w") as file:
    file.write(kml_header + kml_body + kml_footer)

logging.info(f"KML file saved at {kml_filename}")
print(f"KML file saved: {kml_filename}")
