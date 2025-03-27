import cftime
import pytest

import compliance_checker.rulebook.cmiputil

TEST_EXTRACT_DRS_ELEMENTS = {
    "absolute_path": (
        "/element1/element2/element1_element2.nc",
        "<e1>/<e2>",
        "<e1>_<e2>.nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element2"}),
    ),
    "relative_path": (
        "element1/element2/element1_element2.nc",
        "<e1>/<e2>",
        "<e1>_<e2>.nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element2"}),
    ),
    "long_absolute_path": (
        "/element0/element1/element2/element1_element2.nc",
        "<e1>/<e2>",
        "<e1>_<e2>.nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element2"}),
    ),
    "long_relative_path": (
        "element0/element1/element2/element1_element2.nc",
        "<e1>/<e2>",
        "<e1>_<e2>.nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element2"}),
    ),
    "differing_element_values": (
        "/element1/element2/element1_element3.nc",
        "<e1>/<e2>",
        "<e1>_<e2>.nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element3"}),
    ),
    "optional_element_included": (
        "/element1/element2/element1_element3_element4.nc",
        "<e1>/<e2>",
        "<e1>_<e2>[_<e3>].nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element3", "e3": "element4"}),
    ),
    "optional_element_excluded": (
        "/element1/element2/element1_element3.nc",
        "<e1>/<e2>",
        "<e1>_<e2>[_<e3>].nc",
        ({"e1": "element1", "e2": "element2"}, {"e1": "element1", "e2": "element3"}),
    ),
}


@pytest.mark.parametrize(
    "full_path,path_template,filename_template,expected",
    TEST_EXTRACT_DRS_ELEMENTS.values(),
    ids=TEST_EXTRACT_DRS_ELEMENTS.keys(),
)
def test_extract_drs_elements(full_path, path_template, filename_template, expected):
    assert expected == compliance_checker.rulebook.cmiputil.extract_drs_elements(full_path, path_template, filename_template)


TEST_CONVERT_TIME_RANGE_TO_DATETIMES = {
    "month_resolution": (
        "202004-202308",
        "standard",
        (cftime.datetime(2020, 4, 1), cftime.datetime(2023, 8, 1)),
    ),
    "day_resolution": (
        "20200403-20230816",
        "standard",
        (cftime.datetime(2020, 4, 3), cftime.datetime(2023, 8, 16)),
    ),
    "day_resolution_2": (
        "19511201-19551231",
        "standard",
        (cftime.datetime(1951, 12, 1), cftime.datetime(1955, 12, 31)),
    ),
    "hour_resolution": (
        "2020040302-2023081622",
        "standard",
        (cftime.datetime(2020, 4, 3, 2), cftime.datetime(2023, 8, 16, 22)),
    ),
    "minute_resolution": (
        "202004030201-202308162259",
        "standard",
        (cftime.datetime(2020, 4, 3, 2, 1), cftime.datetime(2023, 8, 16, 22, 59)),
    ),
    "day_resolution_360": (
        "20200403-20230816",
        "360_day",
        (cftime.datetime(2020, 4, 3, calendar="360_day"), cftime.datetime(2023, 8, 16, calendar="360_day")),
    ),
}


@pytest.mark.parametrize(
    "time_range,calendar,expected",
    TEST_CONVERT_TIME_RANGE_TO_DATETIMES.values(),
    ids=TEST_CONVERT_TIME_RANGE_TO_DATETIMES.keys(),
)
def test_convert_time_range_to_datetimes(time_range, calendar, expected):
    assert expected == compliance_checker.rulebook.cmiputil.convert_time_range_to_datetimes(time_range, calendar)


TEST_TIME_RANGE_TO_EXPECTED_POINT_COUNT = {
    "mon_standard": ("202004-202308", "mon", "standard", 41),
    "mon_360": ("202004-202308", "mon", "360_day", 41),
    "day_standard": ("20200101-20230101", "day", "standard", 1097),
    "day_standard_2": ("19511201-19551231", "day", "standard", 1492),
    "day_360": ("20200101-20230101", "day", "360_day", 1081),
    "day_365": ("20200101-20230101", "day", "365_day", 1096),
    "6hr_standard": ("2020010100-2020030106", "6hr", "standard", 242),
    "6hr_360": ("2020010100-2020030106", "6hr", "360_day", 242),
    "6hr_standard_minute": ("202001010000-202003010600", "6hr", "standard", 242),
    "3hr_standard": ("2020010100-2020022921", "3hr", "standard", 480),
    "3hr_360": ("2020010100-2020023021", "3hr", "360_day", 480),
    "3hr_standard_minute": ("202001010000-202002292100", "3hr", "standard", 480),
    "1hr_standard": ("2020010100-2020022921", "1hr", "standard", 1438),
    "1hr_360": ("2020010100-2020023021", "1hr", "360_day", 1438),
    "1hr_standard_minute": ("202001010000-202002292100", "1hr", "standard", 1438),
    "1hr_standard_half_hour": ("202001010030-202001312330", "1hr", "standard", 744),
}


@pytest.mark.parametrize(
    "time_range,frequency,calendar,expected",
    TEST_TIME_RANGE_TO_EXPECTED_POINT_COUNT.values(),
    ids=TEST_TIME_RANGE_TO_EXPECTED_POINT_COUNT.keys(),
)
def test_time_range_to_expected_point_count(time_range, frequency, calendar, expected):
    assert expected == compliance_checker.rulebook.cmiputil.time_range_to_expected_point_count(time_range, frequency, calendar)
