import netCDF4
import pytest

from compliance_checker.rulebook import rulebook_imp, rulebook_model


def _assert_all_results(results):
    failed = [result for result in results if not rulebook_imp.result_is_success(result)]
    assert len(failed) == 0, str([result.msgs for result in failed])


def test_rulebook_from_dict(nc_test_file):
    rulebook_dict = {
        "rulebook": "Test rulebook from dict",
        "lookup_table": {"cv": {"domain_id": ["EUR-12"], "variable_id": ["pr"]}},
        "rule_sections": [{"section": "1", "heading": "Format", "rules": [{"data_model": "NETCDF4_CLASSIC"}]}],
    }
    rulebook = rulebook_imp.RuleBookImpl(rulebook_dict)
    _assert_all_results(rulebook.validate(netCDF4.Dataset(nc_test_file)))


def test_rulebook_from_str(nc_test_file):
    rulebook_str = """
    rulebook: "Test rulebook from string"
    rule_sections:
      - section: "1"
        heading: "Format"
        rules:
          - { data_model: "NETCDF4_CLASSIC" }
    """
    rulebook = rulebook_imp.RuleBookImpl.from_str(rulebook_str)
    _assert_all_results(rulebook.validate(netCDF4.Dataset(nc_test_file)))


TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CV = {
    "cv_plain": (
        {"domain_id": ["EUR-12"], "variable_id": ["pr"]},
        rulebook_imp.LookupTableImpl({"cv": {"domain_id": ["EUR-12"], "variable_id": ["pr"]}}),
    ),
}


@pytest.mark.parametrize(
    "cv,expected",
    TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CV.values(),
    ids=TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CV.keys(),
)
def test_rulebook_lookup_table_compile_cv(cv, expected):
    lut = rulebook_imp.LookupTableImpl()
    rulebook_imp.LookupTableCompiler.compile_cv(lut, cv)
    assert lut == expected


TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CF = {
    "cf_plain": (
        rulebook_model.CFLU(axis=[rulebook_model.Axis.T, rulebook_model.Axis.Y, rulebook_model.Axis.X]),
        rulebook_imp.LookupTableImpl({"cf": {"axis": {"T": "time", "Y": "lat", "X": "lon"}}}),
    ),
}


@pytest.mark.parametrize(
    "cf,expected",
    TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CF.values(),
    ids=TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CF.keys(),
)
def test_rulebook_lookup_table_compile_cf(nc_test_file, cf, expected):
    lut = rulebook_imp.LookupTableImpl()
    rulebook_imp.LookupTableCompiler.compile_cf(lut, cf, netCDF4.Dataset(nc_test_file))
    assert lut == expected


TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CMIP = {
    "cmip_plain": (
        rulebook_model.CMIPLU(
            path_drs="<project_id>/<frequency>/<variable_id>",
            file_drs="<variable_id>_<domain_id>_<frequency>[_<time_range>].nc",
            time=rulebook_model.CMIPTimeLU(range="20200101-20201231", frequency="day", variable="time"),
        ),
        rulebook_imp.LookupTableImpl(
            {
                "cmip": {
                    "path_drs": {"project_id": "CORDEX", "frequency": "day", "variable_id": "pr"},
                    "file_drs": {"variable_id": "pr", "domain_id": "EUR-12", "frequency": "day", "time_range": "20200101-20201231"},
                    "time": {"count": 366},
                }
            }
        ),
    ),
    "cmip_with_lookup": (
        rulebook_model.CMIPLU(
            path_drs="<project_id>/<frequency>/<variable_id>",
            file_drs="<variable_id>_<domain_id>_<frequency>[_<time_range>].nc",
            time=rulebook_model.CMIPTimeLU(
                range=rulebook_model.Lookup(lookup="cmip.file_drs.time_range"),
                frequency=rulebook_model.Lookup(lookup="cmip.path_drs.frequency"),
                variable="time",
            ),
        ),
        rulebook_imp.LookupTableImpl(
            {
                "cmip": {
                    "path_drs": {"project_id": "CORDEX", "frequency": "day", "variable_id": "pr"},
                    "file_drs": {"variable_id": "pr", "domain_id": "EUR-12", "frequency": "day", "time_range": "20200101-20201231"},
                    "time": {"count": 366},
                }
            }
        ),
    ),
}


@pytest.mark.parametrize(
    "cmip,expected",
    TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CMIP.values(),
    ids=TEST_RULEBOOK_LOOKUP_TABLE_COMPILE_CMIP.keys(),
)
def test_rulebook_lookup_table_compile_cmip(nc_test_file, cmip, expected):
    lut = rulebook_imp.LookupTableImpl()
    rulebook_imp.LookupTableCompiler.compile_cmip(lut, cmip, netCDF4.Dataset(nc_test_file))
    assert lut == expected
