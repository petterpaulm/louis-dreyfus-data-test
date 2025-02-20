import xarray as xr
import numpy as np
import logging

from logging_config import logging  # Import custom logging setup

def clean_and_transform(ds):
    """Apply data cleaning and transformation steps."""
    if ds is None:
        logging.error("Received empty dataset for cleaning. Exiting...")
        return None

    # Replace missing values
    ds_cleaned = ds.where(ds != -9999, np.nan).fillna(0.0)

    # Convert longitude to [-180, 180] range
    ds_cleaned = ds_cleaned.assign_coords(longitude=((ds_cleaned.longitude + 180) % 360) - 180)
    ds_cleaned = ds_cleaned.sortby(ds_cleaned.longitude)

    # Rename specific variables
    rename_dict = {
        "swvl1": "sw-5",
        "swvl2": "sw-15",
        "swvl3": "sw-50"
    }

    ds_cleaned = ds_cleaned.rename({k: v for k, v in rename_dict.items() if k in ds_cleaned})

    # Save processed dataset
    ds_cleaned.attrs["crs"] = "EPSG:4326"
    ds_cleaned.to_netcdf("Outputs/final_cleaned_dataset.nc")

    logging.info("Final cleaned dataset saved as Outputs/final_cleaned_dataset.nc")

    return ds_cleaned
