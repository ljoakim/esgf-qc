import netCDF4
import numpy as np
import pytest

from compliance_checker.base import Result
from compliance_checker.rulebook import rulebook_impl, rulebook_model


def _check_all_results(results):
    failed = [result for result in results if not rulebook_impl.result_is_success(result)]
    return len(failed) == 0, str([result.msgs for result in failed])


TEST_RESULT_IS_SUCCESS = {
    "bool_success": (Result(value=True), True),
    "bool_fail": (Result(value=False), False),
    "tuple_success": (Result(value=(2,2)), True),
    "tuple_faile": (Result(value=(1,2)), False),
}

@pytest.mark.parametrize(
    "result,expected",
    TEST_RESULT_IS_SUCCESS.values(),
    ids=TEST_RESULT_IS_SUCCESS.keys(),
)
def test_result_is_success(result, expected):
    assert rulebook_impl.result_is_success(result) == expected


TEST_EQUAL_TO_PRECISION = {
    "float_float_success": (1.0e+20, 1.0e+20, True),
    "float_float64_success": (1.0e+20, np.float64(1.0e+20), True),
    "float_float32_success": (1.0e+20, np.float32(1.0e+20), True),
    "float_float32_to_precision_success": (1.0000000200408773e+20, np.float32(1.0e+20), True),
    "float_float32_fail": (1.0e+20, np.float32(1.0000001e+20), False),
    "int_int_success": (2, 2, True),
    "str_str_success": ("2", "2", True),
}

@pytest.mark.parametrize(
    "a,b,expected",
    TEST_EQUAL_TO_PRECISION.values(),
    ids=TEST_EQUAL_TO_PRECISION.keys(),
)
def test_equal_to_precision(a, b, expected):
    assert rulebook_impl.equal_to_precision(a, b) == expected


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
# LookupTableImpl


TEST_LOOKUP_TABLE_IMPL_INST = rulebook_impl.LookupTableImpl(
    {
        "A1": {
            "B": {
                "C1": 1,
                "C2": 2,
            }
        },
        "A2": {
            "B3": 3,
            "B4": 4,
        },
    }
)


TEST_LOOKUP_TABLE_IMPL = {
    "lookup_A1.B.C1": (rulebook_model.Lookup(lookup="A1.B.C1"), 1),
    "lookup_A1.B.C2": (rulebook_model.Lookup(lookup="A1.B.C2"), 2),
    "lookup_A2.B3": (rulebook_model.Lookup(lookup="A2.B3"), 3),
    "lookup_A2.B4": (rulebook_model.Lookup(lookup="A2.B4"), 4),
}


@pytest.mark.parametrize(
    "key,expected",
    TEST_LOOKUP_TABLE_IMPL.values(),
    ids=TEST_LOOKUP_TABLE_IMPL.keys(),
)
def test_lookup_table_impl(key, expected):
    assert TEST_LOOKUP_TABLE_IMPL_INST.lookup(key) == expected


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
    "variable_rule_dimensions_success": (rulebook_model.VariableRule(variable="pr", dimensions=["time", "lat", "lon"]), True),
    "variable_rule_dimensions_fail": (rulebook_model.VariableRule(variable="pr", dimensions=["time", "lon", "lat"]), False),
    "variable_rule_compression_type_success": (rulebook_model.VariableRule(variable="pr", compression_type=rulebook_model.ECompressionType.ZLIB), True),
    "variable_rule_compression_type_fail": (rulebook_model.VariableRule(variable="pr", compression_type=rulebook_model.ECompressionType.NONE), False),
    "variable_rule_compression_level_success": (rulebook_model.VariableRule(variable="pr", compression_level=1), True),
    "variable_rule_compression_level_fail": (rulebook_model.VariableRule(variable="pr", compression_level=0), False),
    "variable_rule_with_single_rule_success": (
        rulebook_model.VariableRule(variable="time", rules=rulebook_model.AttributeRule(attribute="standard_name", must_equal="time")),
        True,
    ),
    "variable_rule_with_single_rule_fail": (
        rulebook_model.VariableRule(variable="time", rules=rulebook_model.AttributeRule(attribute="standard_name", must_equal="incorrect")),
        False,
    ),
    "variable_rule_with_multiple_rules_success": (
        rulebook_model.VariableRule(
            variable="pr",
            rules=[
                rulebook_model.AttributeRule(attribute="standard_name", must_equal="precipitation_flux"),
                rulebook_model.DataRule(dtype="float32"),
            ],
        ),
        True,
    ),
    "variable_rule_with_multiple_rules_fail": (
        rulebook_model.VariableRule(
            variable="pr",
            rules=[
                rulebook_model.AttributeRule(attribute="standard_name", must_equal="precipitation_flux"),
                rulebook_model.DataRule(dtype="float64"),
            ],
        ),
        False,
    ),
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


TEST_RULE_VALIDATOR_VALIDATE_DATA = {
    "data_rule_type_success": ("pr", rulebook_model.DataRule(dtype="float32"), True),
    "data_rule_type_fail": ("pr", rulebook_model.DataRule(dtype="float64"), False),
    "data_rule_byteorder_success": ("pr", rulebook_model.DataRule(dtype="float32", byteorder="="), True),
    "data_rule_byteorder_fail": ("pr", rulebook_model.DataRule(dtype="float32", byteorder=">"), False),
    "data_rule_monotonicity_success": ("time", rulebook_model.DataRule(dtype="float64", monotonicity="<"), True),
    "data_rule_monotonicity_fail": ("time", rulebook_model.DataRule(dtype="float64", monotonicity=">"), False),
    "data_rule_shape_success": ("pr", rulebook_model.DataRule(dtype="float32", shape=[2, 2, 2]), True),
    "data_rule_shape_fail": ("pr", rulebook_model.DataRule(dtype="float32", shape=[2, 2]), False),
    "data_rule_max_success": ("pr", rulebook_model.DataRule(dtype="float32", max=8.0), True),
    "data_rule_max_fail": ("pr", rulebook_model.DataRule(dtype="float32", max=4.0), False),
    "data_rule_min_success": ("pr", rulebook_model.DataRule(dtype="float32", min=1.0), True),
    "data_rule_min_fail": ("pr", rulebook_model.DataRule(dtype="float32", min=4.0), False),
}


@pytest.mark.parametrize(
    "variable,data_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_DATA.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_DATA.keys(),
)
def test_rule_validator_validate_data(nc_test_file, variable, data_rule, expected):
    ds = netCDF4.Dataset(nc_test_file)
    var = ds.variables[variable]
    results = rulebook_impl.RuleValidator.validate_variable_data(var, data_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_VALIDATE_CONDITIONAL = {
    "conditional_rule_single_rule_success": (
        rulebook_model.ConditionalRule(
            condition=rulebook_model.AttributeRule(attribute="domain_id"),
            dependent=rulebook_model.VariableRule(variable="lat"),
        ),
        True,
    ),
    "conditional_rule_multiple_rules_success": (
        rulebook_model.ConditionalRule(
            condition=[
                rulebook_model.AttributeRule(attribute=["domain_id", "variable_id"]),
                rulebook_model.DimensionRule(dimension="lat"),
            ],
            dependent=[
                rulebook_model.VariableRule(variable="lat"),
                rulebook_model.FileFormatRule(data_model="NETCDF4_CLASSIC"),
            ],
        ),
        True,
    ),
    "conditional_rule_condition_not_fulfilled_success": (
        rulebook_model.ConditionalRule(
            condition=rulebook_model.AttributeRule(attribute="noattr"),
            dependent=rulebook_model.VariableRule(variable="novar"),
        ),
        True,
    ),
    "conditional_rule_dependent_not_fulfilled_fail": (
        rulebook_model.ConditionalRule(
            condition=rulebook_model.AttributeRule(attribute="domain_id"),
            dependent=rulebook_model.VariableRule(variable="novar"),
        ),
        False,
    ),
}


@pytest.mark.parametrize(
    "conditional_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_CONDITIONAL.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_CONDITIONAL.keys(),
)
def test_rule_validator_validate_conditional(nc_test_file, conditional_rule, expected):
    results = rulebook_impl.RuleValidator.validate_conditional(netCDF4.Dataset(nc_test_file), conditional_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_VALIDATE_RULE_LIST_LOGIC = {
    "rule_list_logic_rule_single_rule_success": (
        rulebook_model.RuleListLogicRule(
            logic=rulebook_model.ERuleListLogic.ALL,
            rules=rulebook_model.AttributeRule(attribute="domain_id"),
        ),
        True,
    ),
    "rule_list_logic_rule_single_rule_fail": (
        rulebook_model.RuleListLogicRule(
            logic=rulebook_model.ERuleListLogic.ALL,
            rules=rulebook_model.AttributeRule(attribute="noattr"),
        ),
        False,
    ),
    "rule_list_logic_rule_multiple_rules_success": (
        rulebook_model.RuleListLogicRule(
            logic=rulebook_model.ERuleListLogic.EXACTLY_ONE,
            rules=[rulebook_model.AttributeRule(attribute="noattr"), rulebook_model.AttributeRule(attribute="variable_id")],
        ),
        True,
    ),
    "rule_list_logic_rule_multiple_rules_fail": (
        rulebook_model.RuleListLogicRule(
            logic=rulebook_model.ERuleListLogic.EXACTLY_ONE,
            rules=[rulebook_model.AttributeRule(attribute="noattr"), rulebook_model.AttributeRule(attribute="noattr2")],
        ),
        False,
    ),
}


@pytest.mark.parametrize(
    "rule_list_logic_rule,expected",
    TEST_RULE_VALIDATOR_VALIDATE_RULE_LIST_LOGIC.values(),
    ids=TEST_RULE_VALIDATOR_VALIDATE_RULE_LIST_LOGIC.keys(),
)
def test_rule_validator_validate_rule_list_logic(nc_test_file, rule_list_logic_rule, expected):
    results = rulebook_impl.RuleValidator.validate_rule_list_logic(netCDF4.Dataset(nc_test_file), rule_list_logic_rule, rulebook_impl.LookupTableImpl())
    check, msgs = _check_all_results(results)
    assert check == expected, msgs


TEST_RULE_VALIDATOR_EXPAND_RULE = {
    "expand_rule_single_rule": (
        "dimension",
        rulebook_model.DimensionRule(dimension="time"),
        [rulebook_model.DimensionRule(dimension="time")],
    ),
    "expand_rule_multiple_rules": (
        "dimension",
        rulebook_model.DimensionRule(dimension=["time", "lat", "lon"]),
        [rulebook_model.DimensionRule(dimension="time"), rulebook_model.DimensionRule(dimension="lat"), rulebook_model.DimensionRule(dimension="lon")],
    ),
}


@pytest.mark.parametrize(
    "expanding_field_name,rule,expected",
    TEST_RULE_VALIDATOR_EXPAND_RULE.values(),
    ids=TEST_RULE_VALIDATOR_EXPAND_RULE.keys(),
)
def test_rule_validator_expand_rule(expanding_field_name, rule, expected):
    result = rulebook_impl.RuleValidator.expand_rule(expanding_field_name, rule, rulebook_impl.LookupTableImpl())
    assert result == expected


TEST_RULE_VALIDATOR_EVALUATE_RESULT_LIST_LOGIC = {
    "result_list_logic_all_with_all": ([Result(value=True), Result(value=True)], rulebook_model.ERuleListLogic.ALL, True),
    "result_list_logic_one_with_all": ([Result(value=True), Result(value=False)], rulebook_model.ERuleListLogic.ALL, False),
    "result_list_logic_none_with_all": ([Result(value=False), Result(value=False)], rulebook_model.ERuleListLogic.ALL, False),
    "result_list_logic_all_with_exactly_one": ([Result(value=True), Result(value=True)], rulebook_model.ERuleListLogic.EXACTLY_ONE, False),
    "result_list_logic_one_with_exactly_one": ([Result(value=True), Result(value=False)], rulebook_model.ERuleListLogic.EXACTLY_ONE, True),
    "result_list_logic_none_with_exactly_one": ([Result(value=False), Result(value=False)], rulebook_model.ERuleListLogic.EXACTLY_ONE, False),
    "result_list_logic_all_with_at_least_one": ([Result(value=True), Result(value=True)], rulebook_model.ERuleListLogic.AT_LEAST_ONE, True),
    "result_list_logic_one_with_at_least_one": ([Result(value=True), Result(value=False)], rulebook_model.ERuleListLogic.AT_LEAST_ONE, True),
    "result_list_logic_none_with_at_least_one": ([Result(value=False), Result(value=False)], rulebook_model.ERuleListLogic.AT_LEAST_ONE, False),
    "result_list_logic_all_with_none": ([Result(value=True), Result(value=True)], rulebook_model.ERuleListLogic.NONE, False),
    "result_list_logic_one_with_none": ([Result(value=True), Result(value=False)], rulebook_model.ERuleListLogic.NONE, False),
    "result_list_logic_none_with_none": ([Result(value=False), Result(value=False)], rulebook_model.ERuleListLogic.NONE, True),
}


@pytest.mark.parametrize(
    "result_list,logic,expected",
    TEST_RULE_VALIDATOR_EVALUATE_RESULT_LIST_LOGIC.values(),
    ids=TEST_RULE_VALIDATOR_EVALUATE_RESULT_LIST_LOGIC.keys(),
)
def test_rule_validator_evaluate_result_list_logic(result_list, logic, expected):
    result, msg = rulebook_impl.RuleValidator.evaluate_result_list_logic(result_list, logic)
    assert result == expected, msg


##############################################
# RuleBookImpl

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
