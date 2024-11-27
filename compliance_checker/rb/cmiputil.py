import pathlib
import re

import cftime


def extract_drs_elements(full_path: pathlib.Path, drs: str) -> dict[str, str]:
    def match_regex_pattern(regex, string):
        try:
            elements = re.match(regex, str(string)).groupdict()
        except AttributeError as e:
            raise AttributeError(f"Failed to extract DRS elements from string '{string}'") from e
        return elements

    #
    # TODO: Currently not handling optional elements (e.g. time range)
    #
    file_regex = drs.replace("[", r"").replace("]", r"").replace("<", r"(?P<").replace(">", r">.+)")
    drs_elements = match_regex_pattern(file_regex, full_path.name)
    return drs_elements


def convert_time_range_to_datetimes(time_range: str, calendar: str) -> tuple[cftime.datetime, cftime.datetime]:
    try:
        start_time_str, end_time_str = time_range.split("-")
    except ValueError as e:
        raise ValueError(f"Time range ('{time_range}') incorrectly formatted.") from e

    time_formats = [
        "%Y%m%d%H%M",
        "%Y%m%d%H",
        "%Y%m%d",
        "%Y%m",
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
    start_datetime, end_datetime = convert_time_range_to_datetimes(time_range, calendar)
    if frequency == "mon":
        expected_size = (end_datetime.year - start_datetime.year) * 12 + (end_datetime.month - start_datetime.month) + 1
    else:
        expected_time_range: cftime.timedelta = end_datetime - start_datetime
        if frequency == "day":
            expected_size = expected_time_range.days + 1
        elif frequency == "6hr":
            expected_size = (expected_time_range.days + 1) * 4
        elif frequency == "3hr":
            expected_size = (expected_time_range.days + 1) * 8
        elif frequency == "1hr":
            expected_size = (expected_time_range.days + 1) * 24

    return expected_size
