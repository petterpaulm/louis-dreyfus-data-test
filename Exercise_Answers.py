# Import necessary libraries
import xarray as xr
import cfgrib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import glob, os, datetime, tempfile, gc, logging, time
import rioxarray  # Required for GeoTIFF conversion
import eccodes  # Ensures compatibility with GRIB2 files
import colorama

# former color setup that I use to highlight "prints", but we need to refactor that for "logging".
class style():
    HEADER = lambda x: colorama.Fore.BLACK + colorama.Back.CYAN + str(x)
    COMPLEMENT = lambda x: colorama.Fore.RED + str(x)
    RESET = lambda x: colorama.Style.RESET_ALL + str(x)

class ColorFormatter(logging.Formatter):
    """Custom formatter to apply colors based on log level"""
    
    def format(self, record):
        level_colors = {
            logging.DEBUG: style.HEADER(f"[DEBUG]"),
            logging.INFO: style.HEADER(f"[INFO]"),
            logging.WARNING: style.COMPLEMENT(f"[WARNING]"),
            logging.ERROR: style.COMPLEMENT(f"[ERROR]"),
            logging.CRITICAL: style.COMPLEMENT(f"[CRITICAL]"),
        }
        log_color = level_colors.get(record.levelno, style.RESET("[LOG]"))
        log_msg = super().format(record)
        return f"{log_color} {log_msg} {style.RESET('')}"  # Reset color at the end

# Create a console handler with color formatting
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter("%(asctime)s - %(levelname)s - %(message)s"))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set minimum log level
    handlers=[console_handler],  # Use the colored console handler
)

logging.debug("This is a debug message.")
logging.info("Processing started...")
logging.warning("Low memory warning!")
logging.error("File not found!")
logging.critical("Critical system failure!")

#----------- didn't work ----------------------------

# ---------------------------------------------------
# CONFIGURE LOGGING
# ---------------------------------------------------

logging.getLogger().addHandler(logging.StreamHandler())


logging.basicConfig(
    filename="grib2_processing.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger().addHandler(logging.StreamHandler())  # Also print logs to console
logging.info("Starting GRIB2 file processing...")

# ---------------------------------------------------
# PART 1 - FILE EXPLORATION & METADATA EXTRACTION
# ---------------------------------------------------

# List all GRIB2 files in the directory
file_list = sorted(glob.glob("./Data/*.grib2"))

# Extract forecast steps and metadata
init_dict = {}

for filename in file_list:
    parts = filename.split(".")

    if len(parts) < 5:
        logging.warning(f"Skipping file due to unexpected format: {filename}")
        continue

    date_str, hour_str, step_str = parts[3], parts[4], parts[5]
    init_datetime = datetime.datetime.strptime(date_str + hour_str.replace("z", ""), "%Y%m%d%H")
    forecast_step_hours = int(step_str.replace("h", ""))
    valid_datetime = init_datetime + datetime.timedelta(hours=forecast_step_hours)

    if init_datetime not in init_dict:
        init_dict[init_datetime] = {}
    init_dict[init_datetime][forecast_step_hours] = valid_datetime

for init_dt, step_dict in sorted(init_dict.items()):
    logging.info(f'Initialization Time: {init_dt}')
    for step_hr, valid_dt in sorted(step_dict.items()):
        logging.info(f"  Step {step_hr}h → Valid Time: {valid_dt}")

# ---------------------------------------------------
# PART 2 - DATA EXTRACTION AND PROCESSING
# ---------------------------------------------------

datasets = []
temp_files = []

for file_path in file_list:
    try:
        # Load main dataset
        ds_main = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={"indexpath": None})
        datasets.append(ds_main)

        # Load soil variables separately (avoid conflicts with depthBelowLandLayer)
        for depth in [0, 7, 28]:
            try:
                ds_soil = xr.open_dataset(
                    file_path, engine='cfgrib',
                    backend_kwargs={"indexpath": None},
                    filter_by_keys={"depthBelowLandLayer": depth}
                )
                datasets.append(ds_soil)
            except Exception as e:
                logging.warning(f"Skipping depth {depth} for {file_path}: {e}")

        # Save intermediate results to temporary NetCDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
            temp_path = tmp.name
            ds_main.to_netcdf(temp_path)
            temp_files.append(temp_path)

        del ds_main  # Free memory
        gc.collect()

    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")

logging.info("All files processed. Merging datasets...")

# Merge datasets safely
ds_combined = xr.open_mfdataset(temp_files, combine="nested", concat_dim="step")

# ---------------------------------------------------
# PART 3 - DATA CLEANING & TRANSFORMATION
# ---------------------------------------------------

# Function to handle missing values
def clean_missing_values(ds, fill_value=0.0, sentinel=-9999):
    ds_cleaned = ds.where(ds != sentinel, np.nan).fillna(fill_value)
    return ds_cleaned

ds_clean = clean_missing_values(ds_combined)

# Convert longitude from [0, 360] to [-180, 180]
ds_clean = ds_clean.assign_coords(longitude=((ds_clean.longitude + 180) % 360) - 180)
ds_clean = ds_clean.sortby(ds_clean.longitude)

# Rename variables
rename_dict = {
    "swvl1": "sw-5",
    "swvl2": "sw-15",
    "swvl3": "sw-50"
}

ds_renamed = ds_clean.rename({k: v for k, v in rename_dict.items() if k in ds_clean})

# Save processed dataset
ds_renamed.attrs["crs"] = "EPSG:4326"
ds_renamed.to_netcdf("final_dataset.nc")
logging.info("Final dataset saved as final_dataset.nc")

# ---------------------------------------------------
# PART 4 - PERFORMANCE AND OPTIMIZATION
# ---------------------------------------------------

# Ensure all datasets are closed before deletion
for temp_file in temp_files:
    try:
        ds = xr.open_dataset(temp_file)
        ds.close()
    except Exception as e:
        logging.warning(f"Could not open {temp_file} before deletion: {e}")

# Force garbage collection to release file locks
del ds_combined
gc.collect()

# Retry file deletion with a delay
for temp_file in temp_files:
    for attempt in range(5):  # Retry up to 5 times
        try:
            os.remove(temp_file)
            logging.info(f"Deleted temp file: {temp_file}")
            break  # Successfully deleted
        except PermissionError:
            logging.warning(f"Retrying deletion of {temp_file}... (attempt {attempt+1}/5)")
            time.sleep(2)  # Wait before retrying

logging.info("All temporary files deleted.")

# ---------------------------------------------------
# BONUS TASK: EXPORT FOR VISUALIZATION
# ---------------------------------------------------

# Convert to GeoTIFF
try:
    ds = xr.open_dataset("final_dataset.nc")
    ds["t2m"].rio.write_crs("EPSG:4326").rio.to_raster("temperature_2m.tif")
    logging.info("GeoTIFF file saved as temperature_2m.tif")
except Exception as e:
    logging.error(f"Error saving GeoTIFF: {e}")

# Convert to CSV
try:
    ds.to_dataframe().to_csv("final_dataset.csv")
    logging.info("CSV file saved as final_dataset.csv")
except Exception as e:
    logging.error(f"Error saving CSV: {e}")

# Convert to Zarr for Azure
try:
    ds.to_zarr("final_dataset.zarr", consolidated=True)
    logging.info("Zarr file saved as final_dataset.zarr")
except Exception as e:
    logging.error(f"Error saving Zarr: {e}")

logging.info("All processing steps completed successfully!")






# ---------------------------------------------------
# PLAYING WITH THE DATA
# ---------------------------------------------------

# ---------------------------------------------------
# Generating a GIF
# ---------------------------------------------------

file_list = sorted(glob.glob("./Data/*.grib2"))

# Open all files and concatenate them along the step dimension
ds_combined = xr.open_mfdataset(file_list, combine="nested", concat_dim="step", engine="cfgrib")

print(ds_combined["step"].values)

# Load combined dataset with multiple forecast steps
if "step" in ds_combined.coords and ds_combined["step"].size > 1:
    step_values = ds_combined["step"].values  # Get all forecast steps
    valid_times = ds_combined["valid_time"].values  # Get corresponding valid times

    fig, ax = plt.subplots(figsize=(12, 6), subplot_kw={"projection": ccrs.PlateCarree()})
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linestyle=":")
    ax.add_feature(cfeature.LAND, facecolor="lightgray")

    # Define color map
    cmap = plt.get_cmap("coolwarm")

    # Get min and max values for consistent color scaling
    t2m_min = (ds_combined["t2m"] - 273.15).min().values
    t2m_max = (ds_combined["t2m"] - 273.15).max().values

    # Initialize plot
    im = ax.pcolormesh(ds_combined.longitude, ds_combined.latitude, ds_combined["t2m"].isel(step=0) - 273.15,
                       cmap=cmap, vmin=t2m_min, vmax=t2m_max, transform=ccrs.PlateCarree())

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, orientation="horizontal", pad=0.05)
    cbar.set_label("2m Temperature (°C)", fontsize=12)

    def update(frame):
        """Update function for animation"""
        im.set_array((ds_combined["t2m"].isel(step=frame) - 273.15).values.ravel())
        ax.set_title(f"2m Temperature at {valid_times[frame]}", fontsize=14)
        return im,

    # Create animation
    ani = animation.FuncAnimation(fig, update, frames=len(step_values), interval=500, blit=False)

    # Save animation as GIF
    ani.save("temperature_forecast.gif", dpi=100, writer="pillow")
    
    logging.info("GIF saved as 'temperature_forecast.gif'")

    plt.show()
else:
    logging.warning("No multiple forecast steps found. Only one step available.")

# ---------------------------------------------------
# 3D Temp map
# ---------------------------------------------------

from mpl_toolkits.mplot3d import Axes3D

# Convert temperature to Celsius
t2m_celsius = ds_combined["t2m"].isel(step=0) - 273.15

# Ensure data is loaded into memory (fixes Dask issue)
t2m_celsius = t2m_celsius.compute()

# Convert longitude from [0, 360] to [-180, 180]
ds_combined = ds_combined.assign_coords(longitude=((ds_combined.longitude + 180) % 360) - 180)

# Sort longitude properly
sorted_indices = np.argsort(ds_combined.longitude.values)
sorted_longitude = ds_combined.longitude.values[sorted_indices]

# Create meshgrid for 3D plotting (must use sorted longitudes)
lon, lat = np.meshgrid(sorted_longitude, ds_combined.latitude.values)

# Ensure temperature data is correctly ordered
t2m_sorted = t2m_celsius.values[:, sorted_indices]

# Create figure
fig = plt.figure(figsize=(12, 6))
ax = fig.add_subplot(111, projection='3d')

# Plot surface with correctly aligned longitude, latitude, and temperature
surf = ax.plot_surface(lon, lat, t2m_sorted, cmap="coolwarm", edgecolor="none")

# Add colorbar
cbar = fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
cbar.set_label("2m Temperature (°C)")

# Set proper limits for a realistic 3D globe
ax.set_xlim([-180, 180])
ax.set_ylim([-90, 90])
ax.set_zlim([t2m_sorted.min(), t2m_sorted.max()])

# Labels and title
ax.set_xlabel("Longitude (°)")
ax.set_ylabel("Latitude (°)")
ax.set_zlabel("Temperature (°C)")
ax.set_title("3D Temperature Map with Corrected Longitude")

# Show plot
plt.show()


# ---------------------------------------------------
# Converting to Google Earth KML (as we can it there)
# ---------------------------------------------------

import xarray as xr
import numpy as np
import os

# Load dataset
ds = xr.open_dataset("final_dataset.nc")

# Extract temperature in Celsius
t2m_celsius = ds["t2m"].isel(step=0) - 273.15

# Convert longitude from [0, 360] to [-180, 180]
ds = ds.assign_coords(longitude=((ds.longitude + 180) % 360) - 180)

# Define the folder and filename
output_folder = "./Data/"
os.makedirs(output_folder, exist_ok=True)  # Ensure the folder exists
kml_filename = os.path.join(output_folder, "temperature_data.kml")

# Define color scale based on temperature range (adjust min/max as needed)
temp_min, temp_max = -30, 50  # Adjust according to your dataset
color_palette = [
    "#0000FF",  # Blue (Cold)
    "#00FFFF",  # Cyan
    "#00FF00",  # Green
    "#FFFF00",  # Yellow
    "#FF7F00",  # Orange
    "#FF0000"   # Red (Hot)
]

def get_color(temp):
    """Assigns a color based on temperature."""
    norm_temp = np.clip((temp - temp_min) / (temp_max - temp_min), 0, 1)
    index = int(norm_temp * (len(color_palette) - 1))
    return color_palette[index]

# Create KML header
kml_header = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
"""

# Generate KML Placemarks with colored icons
kml_body = ""
for lat in ds.latitude.values[::5]:  # Reduce points to avoid clutter
    for lon in ds.longitude.values[::5]:
        temp_value = t2m_celsius.sel(latitude=lat, longitude=lon, method="nearest").values
        color = get_color(temp_value)
        kml_body += f"""
<Placemark>
  <name>{temp_value:.1f}°C</name>
  <Style>
    <IconStyle>
      <color>{color.replace("#", "ff")}</color>  <!-- Convert hex to KML format -->
      <scale>0.6</scale>
      <Icon>
        <href>http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png</href>
      </Icon>
    </IconStyle>
  </Style>
  <Point>
    <coordinates>{lon},{lat},0</coordinates>
  </Point>
</Placemark>
"""

# Close KML file
kml_footer = """</Document></kml>"""

# Save KML file
with open(kml_filename, "w") as file:
    file.write(kml_header + kml_body + kml_footer)

print(f"✅ KML file saved with colors: {kml_filename}")
print("📂 Open the file in Google Earth to see colored temperature markers.")


