import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import logging

from logging_config import logging  # Import logging setup

logging.info("Generating 3D temperature map...")

# Load dataset with error handling
try:
    ds = xr.open_dataset("Outputs/final_dataset.nc")
    logging.info("Successfully loaded Outputs/final_dataset.nc")
    logging.info(f"Available variables: {list(ds.data_vars.keys())}")
except Exception as e:
    logging.error(f"Error loading dataset: {e}")
    exit()

# Ensure 't2m' exists in dataset
if "t2m" not in ds:
    raise KeyError("The dataset does not contain the variable 't2m'. Check your NetCDF file.")

# Convert temperature to Celsius and ensure data is loaded into memory
t2m_celsius = ds["t2m"].isel(step=0) - 273.15
t2m_celsius = t2m_celsius.compute()

# Convert longitude from [0, 360] to [-180, 180]
ds = ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180)
ds = ds.sortby(ds.longitude)  # Sort longitudes for proper plotting

# Extract coordinates
lon, lat = np.meshgrid(ds.longitude.values, ds.latitude.values)

# Ensure temperature data aligns properly
t2m_sorted = t2m_celsius.values

# Create 3D figure
fig = plt.figure(figsize=(12, 6))
ax = fig.add_subplot(111, projection='3d')

# Plot surface with correctly aligned longitude, latitude, and temperature
surf = ax.plot_surface(lon, lat, t2m_sorted, cmap="coolwarm", edgecolor="none")

# Add colorbar manually (avoiding common `None` issues)
mappable = plt.cm.ScalarMappable(cmap="coolwarm")
mappable.set_array(t2m_sorted)
cbar = fig.colorbar(mappable, ax=ax, shrink=0.5, aspect=5)
cbar.set_label("2m Temperature (°C)")

# Set axis labels and title
ax.set_xlabel("Longitude (°)")
ax.set_ylabel("Latitude (°)")
ax.set_zlabel("Temperature (°C)")
ax.set_title("3D Temperature Map")

# Save and display
output_file = "Outputs/3d_map.png"
plt.savefig(output_file)
logging.info(f"3D Temperature map saved as {output_file}")
plt.show()
