import xarray as xr
import cfgrib
import glob
import datetime
import logging
import os
import tempfile
import gc

from logging_config import logging  # Import custom logging setup

def process_grib_files():
    """Process GRIB2 files and extract data."""
    logging.info("Starting GRIB2 file processing...")

    # List all GRIB2 files
    file_list = sorted(glob.glob("./Data/*.grib2"))

    if not file_list:
        logging.error("No GRIB2 files found in ./Data/. Exiting...")
        return None

    temp_files = []

    for file_path in file_list:
        try:
            # Open dataset with all available variables (without filtering)
            ds_main = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={"indexpath": None})
            datasets = [ds_main]  # Store all processed datasets

            # Extract specific variables (Fixing depthBelowLandLayer issue)
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

            # Merge all datasets per file
            ds_merged = xr.merge(datasets, combine_attrs="override")

            # Save to temporary NetCDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
                temp_path = tmp.name
                ds_merged.to_netcdf(temp_path)
                temp_files.append(temp_path)

            del ds_main, ds_merged, datasets  # Free memory
            gc.collect()

        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")

    if not temp_files:
        logging.error("No NetCDF files were created. Exiting...")
        return None

    # Merge all NetCDFs together
    try:
        ds_combined = xr.open_mfdataset(temp_files, combine="nested", concat_dim="step")
    except Exception as e:
        logging.error(f"Failed to merge datasets: {e}")
        return None

    output_path = "Outputs/final_dataset.nc"
    ds_combined.to_netcdf(output_path)

    logging.info(f"Final dataset saved as {output_path}")

    return ds_combined
