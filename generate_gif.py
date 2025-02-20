import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import logging

from logging_config import logging  # Import custom logging setup

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

# Ensure forecast steps exist
if "step" not in ds.coords:
    raise KeyError("The dataset does not contain the 'step' coordinate. Cannot animate time steps.")

# Extract key information
temperature = ds["t2m"] - 273.15  # Convert to Celsius
steps = ds["step"].values  # Forecast steps
valid_times = ds["valid_time"].values  # Time at each step

logging.info(f"Forecast Steps: {steps}")
logging.info(f"Valid Times: {valid_times}")

# Create figure with Cartopy projection
fig, ax = plt.subplots(figsize=(12, 6), subplot_kw={"projection": ccrs.PlateCarree()})
ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
ax.add_feature(cfeature.BORDERS, linestyle=":")
ax.add_feature(cfeature.LAND, facecolor="lightgray")

# Define color map
cmap = plt.get_cmap("coolwarm")
t2m_min, t2m_max = temperature.min().values, temperature.max().values

# Initialize first frame
im = ax.pcolormesh(
    ds.longitude, ds.latitude, temperature.isel(step=0),
    cmap=cmap, vmin=t2m_min, vmax=t2m_max, transform=ccrs.PlateCarree()
)

# Add colorbar
cbar = plt.colorbar(im, ax=ax, orientation="horizontal", pad=0.05)
cbar.set_label("2m Temperature (°C)", fontsize=12)

# Define animation update function
def update(frame):
    im.set_array(temperature.isel(step=frame).values.ravel())  # Update data
    ax.set_title(f"2m Temperature Forecast for {valid_times[frame]}", fontsize=14)
    return im,

# Create animation
ani = animation.FuncAnimation(fig, update, frames=len(steps), interval=500, blit=False)

# Save animation as GIF
gif_filename = "Outputs/temperature_forecast.gif"
ani.save(gif_filename, dpi=100, writer="pillow")

logging.info(f"GIF saved as '{gif_filename}'")
plt.show()
