import netCDF4
import pytest

from compliance_checker.rulebook import rulebook_impl, rulebook_model


def _check_all_results(results):
    failed = [result for result in results if not rulebook_impl.result_is_success(result)]
    return len(failed) == 0, str([result.msgs for result in failed])


def test_rulebook_from_dict(nc_test_file):
    rulebook_dict = {
        "rulebook": "Test rulebook from dict",
        "lookup_table": {"cv": {"domain_id": ["EUR-12"], "variable_id": ["pr"]}},
        "rule_sections": [{"section": "1", "heading": "Format", "rules": [{"data_model": "NETCDF4_CLASSIC"}]}],
    }
    rulebook = rulebook_impl.RuleBookImpl(rulebook_dict)
    assert _check_all_results(rulebook.validate(netCDF4.Dataset(nc_test_file)))


def test_rulebook_from_str(nc_test_file):
    rulebook_str = """
    rulebook: "Test rulebook from string"
    rule_sections:
      - section: "1"
        heading: "Format"
        rules:
          - { data_model: "NETCDF4_CLASSIC" }
    """
    rulebook = rulebook_impl.RuleBookImpl.from_str(rulebook_str)
    assert _check_all_results(rulebook.validate(netCDF4.Dataset(nc_test_file)))


##############################################
# LookupTableCompiler


TEST_LOOKUP_TABLE_COMPILER_COMPILE_CV = {
    "cv_plain": (
        {"domain_id": ["EUR-12"], "variable_id": ["pr"]},
        rulebook_impl.LookupTableImpl({"cv": {"domain_id": ["EUR-12"], "variable_id": ["pr"]}}),
    ),
}


@pytest.mark.parametrize(
    "cv,expected",
    TEST_LOOKUP_TABLE_COMPILER_COMPILE_CV.values(),
    ids=TEST_LOOKUP_TABLE_COMPILER_COMPILE_CV.keys(),
)
def test_lookup_table_compiler_compile_cv(cv, expected):
    lut = rulebook_impl.LookupTableImpl()
    rulebook_impl.LookupTableCompiler.compile_cv(lut, cv)
    assert lut == expected


TEST_LOOKUP_TABLE_COMPILER_COMPILE_CF = {
    "cf_plain": (
        rulebook_model.LUCF(axis=[rulebook_model.EAxis.T, rulebook_model.EAxis.Y, rulebook_model.EAxis.X]),
        rulebook_impl.LookupTableImpl({"cf": {"axis": {"T": "time", "Y": "lat", "X": "lon"}}}),
    ),
}


@pytest.mark.parametrize(
    "cf,expected",
    TEST_LOOKUP_TABLE_COMPILER_COMPILE_CF.values(),
    ids=TEST_LOOKUP_TABLE_COMPILER_COMPILE_CF.keys(),
)
def test_lookup_table_compiler_compile_cf(nc_test_file, cf, expected):
    lut = rulebook_impl.LookupTableImpl()
    rulebook_impl.LookupTableCompiler.compile_cf(lut, cf, netCDF4.Dataset(nc_test_file))
    assert lut == expected


TEST_LOOKUP_TABLE_COMPILER_COMPILE_CMIP = {
    "cmip_plain": (
        rulebook_model.LUCMIP(
            path_drs="<project_id>/<frequency>/<variable_id>",
            file_drs="<variable_id>_<domain_id>_<frequency>[_<time_range>].nc",
            time=rulebook_model.LUCMIPTime(range="20200101-20201231", frequency="day", variable="time"),
        ),
        rulebook_impl.LookupTableImpl(
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
        rulebook_model.LUCMIP(
            path_drs="<project_id>/<frequency>/<variable_id>",
            file_drs="<variable_id>_<domain_id>_<frequency>[_<time_range>].nc",
            time=rulebook_model.LUCMIPTime(
                range=rulebook_model.Lookup(lookup="cmip.file_drs.time_range"),
                frequency=rulebook_model.Lookup(lookup="cmip.path_drs.frequency"),
                variable="time",
            ),
        ),
        rulebook_impl.LookupTableImpl(
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
    TEST_LOOKUP_TABLE_COMPILER_COMPILE_CMIP.values(),
    ids=TEST_LOOKUP_TABLE_COMPILER_COMPILE_CMIP.keys(),
)
def test_lookup_table_compiler_compile_cmip(nc_test_file, cmip, expected):
    lut = rulebook_impl.LookupTableImpl()
    rulebook_impl.LookupTableCompiler.compile_cmip(lut, cmip, netCDF4.Dataset(nc_test_file))
    assert lut == expected


##############################################
# RuleValidator


TEST_RULE_VALIDATOR_VALIDATE_RULE_SECTION = {
    "rule_section_with_format_rule": (
        rulebook_model.RuleSection(
            section="1",
            heading="Test section",
            rules=rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC"),
        ),
        ["§1 Test section"],
    ),
    "rule_section_with_format_rule_in_list": (
        rulebook_model.RuleSection(
            section="2",
            heading="Test section",
            rules=[rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC")],
        ),
        ["§2 Test section"],
    ),
}


@pytest.mark.parametrize(
    "rule_section,expected_result_name",
    TEST_RULE_VALIDATOR_VALIDATE_RULE_SECTION.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_RULE_SECTION.keys(),
)
def test_rule_validator_validate_rule_section(nc_test_file, rule_section, expected_result_name):
    results = rulebook_impl.RuleValidator.validate_rule_section(netCDF4.Dataset(nc_test_file), rule_section, rulebook_impl.LookupTableImpl())
    assert _check_all_results(results)
    assert results[0].name == expected_result_name
    assert len(results) == 1


TEST_RULE_VALIDATOR_VALIDATE_RULE_OR_RULE_LIST = {
    "rule_or_rule_list_one_rule": (rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC"), True),
    "rule_or_rule_list_two_rules": (
        [
            rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC"),
            rulebook_model.DimensionRule(dimension="time"),
        ],
        True,
    ),
    "rule_or_rule_list_one_rule_fail": (rulebook_model.FileFormatRule(data_model="NETCDF4"), False),
    "rule_or_rule_list_two_rules_fail": (
        [
            rulebook_model.FileFormatRule(data_model="NETCDF4"),
            rulebook_model.DimensionRule(dimension="nodim"),
        ],
        False,
    ),
}


@pytest.mark.parametrize(
    "rule_list,expected",
    TEST_RULE_VALIDATOR_VALIDATE_RULE_OR_RULE_LIST.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_RULE_OR_RULE_LIST.keys(),
)
def test_rule_validator_validate_rule_or_rule_list(nc_test_file, rule_list, expected):
    results = rulebook_impl.RuleValidator.validate_rule_or_rule_list(netCDF4.Dataset(nc_test_file), rule_list, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_VALIDATE_FORMAT = {
    "format_rule_success": (rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC"), True),
    "format_rule_fail": (rulebook_model.FileFormatRule(data_model="NETCDF4"), False),
}


@pytest.mark.parametrize(
    "format_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_FORMAT.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_FORMAT.keys(),
)
def test_rule_validator_validate_format(nc_test_file, format_rule, expected):
    results = rulebook_impl.RuleValidator.validate_format(netCDF4.Dataset(nc_test_file), format_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs
    assert len(results) == 1


TEST_RULE_VALIDATOR_VALIDATE_DIMENSION = {
    "dimension_rule_existance_success": (rulebook_model.DimensionRule(dimension="lat"), True),
    "dimension_rule_existance_fail": (rulebook_model.DimensionRule(dimension="nodim"), False),
    "dimension_rule_existance_expand_success": (rulebook_model.DimensionRule(dimension=["lat", "lon"]), True),
    "dimension_rule_existance_expand_fail": (rulebook_model.DimensionRule(dimension=["lat", "nodim"]), False),
    "dimension_rule_not_required": (rulebook_model.DimensionRule(dimension="nodim", required=False), True),
    "dimension_rule_size_success": (rulebook_model.DimensionRule(dimension="lat", size=2), True),
    "dimension_rule_size_fail": (rulebook_model.DimensionRule(dimension="lat", size=3), False),
}


@pytest.mark.parametrize(
    "dimension_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_DIMENSION.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_DIMENSION.keys(),
)
def test_rule_validator_validate_dimension(nc_test_file, dimension_rule, expected):
    results = rulebook_impl.RuleValidator.validate_dimension(netCDF4.Dataset(nc_test_file), dimension_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_VALIDATE_ATTRIBUTE = {
    "attribute_rule_existance_success": (rulebook_model.AttributeRule(attribute="domain_id"), True),
    "attribute_rule_existance_fail": (rulebook_model.AttributeRule(attribute="noattr"), False),
    "attribute_rule_existance_expand_success": (rulebook_model.AttributeRule(attribute=["domain_id", "variable_id"]), True),
    "attribute_rule_existance_expand_fail": (rulebook_model.AttributeRule(attribute=["domain_id", "noattr"]), False),
    "attribute_rule_not_required": (rulebook_model.AttributeRule(attribute="noattr", required=False), True),
    "attribute_rule_must_equal_success": (rulebook_model.AttributeRule(attribute="domain_id", must_equal="EUR-12"), True),
    "attribute_rule_must_equal_fail": (rulebook_model.AttributeRule(attribute="domain_id", must_equal="EUR-11"), False),
    "attribute_rule_allowed_values_success": (rulebook_model.AttributeRule(attribute="domain_id", allowed_values=["EUR-11", "EUR-12"]), True),
    "attribute_rule_allowed_values_fail": (rulebook_model.AttributeRule(attribute="domain_id", allowed_values=["EUR-11", "AFR-1"]), False),
    "attribute_rule_pattern_success": (rulebook_model.AttributeRule(attribute="variable_id", pattern=r"^pr$"), True),
    "attribute_rule_pattern_fail": (rulebook_model.AttributeRule(attribute="variable_id", pattern=r"^tas$"), False),
}


@pytest.mark.parametrize(
    "attribute_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_ATTRIBUTE.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_ATTRIBUTE.keys(),
)
def test_rule_validator_validate_attribute(nc_test_file, attribute_rule, expected):
    results = rulebook_impl.RuleValidator.validate_attribute(netCDF4.Dataset(nc_test_file), attribute_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_VALIDATE_VARIABLE = {
    "variable_rule_existance_success": (rulebook_model.VariableRule(variable="lat"), True),
    "variable_rule_existance_fail": (rulebook_model.VariableRule(variable="novar"), False),
    "variable_rule_existance_expand_success": (rulebook_model.VariableRule(variable=["lat", "lon"]), True),
    "variable_rule_existance_expand_fail": (rulebook_model.VariableRule(variable=["lat", "novar"]), False),
    "variable_rule_not_required": (rulebook_model.VariableRule(variable="novar", required=False), True),
}


@pytest.mark.parametrize(
    "variable_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_VARIABLE.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_VARIABLE.keys(),
)
def test_rule_validator_validate_variable(nc_test_file, variable_rule, expected):
    results = rulebook_impl.RuleValidator.validate_variable(netCDF4.Dataset(nc_test_file), variable_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs
