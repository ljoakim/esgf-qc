import pathlib

import netCDF4
import pytest


@pytest.fixture(scope="session")
def nc_test_file(tmp_path_factory):
    path_to_file = tmp_path_factory.mktemp("testdata") / "CORDEX" / "day" / "pr"
    path_to_file.mkdir(parents=True, exist_ok=True)
    full_path = path_to_file / "pr_EUR-12_day_20200101-20201231.nc"
    with netCDF4.Dataset(full_path, "w", format="NETCDF4_CLASSIC") as ds:
        # Dimensions
        ds.createDimension("time", None)
        ds.createDimension("lat", 2)
        ds.createDimension("lon", 2)

        # Global attributes
        ds.domain_id = "EUR-12"
        ds.variable_id = "pr"

        # Coordinate variables
        time = ds.createVariable("time", "f8", ("time",))
        time.standard_name = "time"
        time.axis = "T"
        time.calendar = "standard"
        time[:] = [0.0, 1.0]

        lat = ds.createVariable("lat", "f8", ("lat",))
        lat.axis = "Y"
        lat[:] = [0.0, 1.0]

        lon = ds.createVariable("lon", "f8", ("lon",))
        lon.axis = "X"
        lon[:] = [0.0, 1.0]

        # Data variable
        pr = ds.createVariable("pr", "f4", ("time", "lat", "lon"), zlib=True, complevel=1)
        pr.standard_name = "precipitation_flux"
        pr[:] = [[[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]]]

    return full_path
