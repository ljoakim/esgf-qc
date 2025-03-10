import pytest

import compliance_checker.rulebook.cmiputil

TEST_EXTRACT_DRS_ELEMENTS_FROM_PATH = {
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
    TEST_EXTRACT_DRS_ELEMENTS_FROM_PATH.values(),
    ids=TEST_EXTRACT_DRS_ELEMENTS_FROM_PATH.keys(),
)
def test_extract_drs_elements(full_path, path_template, filename_template, expected):
    assert expected == compliance_checker.rulebook.cmiputil.extract_drs_elements(full_path, path_template, filename_template)
