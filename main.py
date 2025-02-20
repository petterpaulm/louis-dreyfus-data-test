import sys
import os

project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)
sys.path.append(project_dir)

from logging_config import logging
import data_extraction
import data_cleaning
import generate_gif
import generate_3d_map
import export_to_kml

logging.info("Executing complete GRIB2 processing pipeline...")

# Extract GRIB2 Data
extracted_ds = data_extraction.process_grib_files()

if extracted_ds is None:
    logging.error("Data extraction failed. Exiting...")
    sys.exit(1)

# Clean Data
cleaned_ds = data_cleaning.clean_and_transform(extracted_ds)

if cleaned_ds is None:
    logging.error("Data cleaning failed. Exiting...")
    sys.exit(1)

# Generate GIF
generate_gif.create_temperature_gif()

# Generate 3D Map
generate_3d_map.create_3d_temperature_map()

# Export to KML
export_to_kml.export_kml()

logging.info("All processing steps completed successfully!")
