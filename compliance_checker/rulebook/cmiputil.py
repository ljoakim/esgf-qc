import pathlib
import re

import cftime


def _match_regex_pattern(regex: str, string: str) -> dict[str, str]:
    try:
        elements = re.match(regex, str(string)).groupdict()
    except AttributeError as e:
        raise AttributeError(f"Failed to extract elements from string: '{string}' is incorrectly formatted.") from e
    return elements


def extract_drs_elements(
    full_path: pathlib.Path,
    path_drs: str = "",
    file_drs: str = "",
) -> dict[str, str]:
    """Extract DRS elements from a path.

    Get DRS elements from path given a DRS specification.

    Parameters
    ----------
    full_path : pathlib.Path
        Full path, including file name, to extract DRS elements from.
    path_drs : str
        DRS specification of path, i.e. full_path excluding filename.
        The template should be formatted with DRS elements enclosed
        by "<" and ">", with "/" separating the
        elements, e.g.:
            "<var1>/<var2>/<var3>"
    file_drs: str
        Template of filename part of full_path. The template should
        be formatted with DRS elements enclosed by "<" and ">". For
        the function to work, the elements must be separated with
        other characters. For CMIP-like DRS specifications, the elements
        are generally separated using an underscore, "_".
        Generally a time range is specified at the end of a netCDF4
        file, whenever there is a variable with a time dimension.
        This optional part must be at the end, and should be
        enclosed by "[" and "]".
        Example:
            "<var1>_<var2>_<var3>[_<time_range>].nc"

    Returns
    -------
    dict[str, str]
        Two dictionaries of DRS elements.

    Raises
    ------
    AttributeError
        If DRS element extraction failed.
    """
    full_path = pathlib.Path(full_path)

    path_drs_elements = {}
    if path_drs:
        path_regex = r"(.*/)?" + path_drs.replace("<", r"(?P<").replace(">", r">.+)") + r"$"
        path_drs_elements = _match_regex_pattern(path_regex, full_path.parent)

    file_drs_elements = {}
    if file_drs:
        try:
            file_regex = file_drs.replace("[", r"").replace("]", r"").replace("<", r"(?P<").replace(">", r">.+)")
            file_drs_elements = _match_regex_pattern(file_regex, full_path.name)
        except AttributeError:
            # Try without optional element
            file_drs = file_drs[: file_drs.index("[")] + file_drs[file_drs.index("]") + 1 :]
            file_regex = file_drs.replace("<", r"(?P<").replace(">", r">.+)")
            file_drs_elements = _match_regex_pattern(file_regex, full_path.name)

    return (path_drs_elements, file_drs_elements)


def convert_time_range_to_datetimes(time_range: str, calendar: str) -> tuple[cftime.datetime, cftime.datetime]:
    """Convert a CMIP-like time range string to cftime datetime objects.

    Parameters
    ----------
    time_range : str
        Time range string.
    calendar : str
        Calendar to use for output cftime datetime objects.

    Returns
    -------
    tuple[cftime.datetime, cftime.datetime]
        Start and end of range.

    Raises
    ------
    ValueError
        If string could not be converted.
    """
    try:
        start_time_str, end_time_str = time_range.split("-")
    except ValueError as e:
        raise ValueError(f"Time range ('{time_range}') incorrectly formatted.") from e

    time_formats = [
        "%Y%m",
        "%Y%m%d",
        "%Y%m%d%H",
        "%Y%m%d%H%M",
    ]
    for time_format in time_formats:
        try:
            start_datetime = cftime.datetime.strptime(start_time_str, time_format, calendar)
            end_datetime = cftime.datetime.strptime(end_time_str, time_format, calendar)
            return start_datetime, end_datetime
        except ValueError:
            pass
    raise ValueError(f"Time range format not supported: '{time_range}'")


def time_range_to_expected_point_count(time_range: str, frequency: str, calendar: str) -> int:
    """Calculate expected number of data points for time range.



    Parameters
    ----------
    time_range : str
        Time range string.
    frequency : str
        Frequency of data points, "mon", "day", "6hr", "3hr" or "1hr".
    calendar : str
        Calendar to use for calculation.

    Returns
    -------
    int
        Expected number of data points.
    """
    start_datetime, end_datetime = convert_time_range_to_datetimes(time_range, calendar)
    if frequency == "mon":
        expected_size = (end_datetime.year - start_datetime.year) * 12 + (end_datetime.month - start_datetime.month) + 1
    else:
        expected_time_range: cftime.timedelta = end_datetime - start_datetime
        hours = expected_time_range.days * 24 + expected_time_range.seconds // 3600
        if frequency == "day":
            expected_size = expected_time_range.days + 1
        elif frequency == "6hr":
            expected_size = hours // 6 + 1
        elif frequency == "3hr":
            expected_size = hours // 3 + 1
        elif frequency == "1hr":
            expected_size = hours + 1
        else:
            raise ValueError(f"Unknown frequency '{frequency}'")

    return expected_size
