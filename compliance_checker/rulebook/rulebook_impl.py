from __future__ import annotations

import pathlib
import re
import typing

import colorama
import netCDF4
import numpy as np
import yaml

from compliance_checker import cfutil
from compliance_checker.base import BaseCheck, Result, TestCtx
from compliance_checker.rulebook import cmiputil, rulebook_model


def result_is_success(result: Result) -> bool:
    if isinstance(result.value, tuple):
        return result.value[0] == result.value[1]
    return result.value


def equal_or_equal_to_precision(a: typing.Any, b: typing.Any) -> bool:
    float_types = (float, np.float32, np.float64)
    if isinstance(a, float_types) or isinstance(b, float_types):
        if isinstance(a, np.float32):
            return a == np.float32(b)
        else:
            return np.float64(a) == np.float64(b)
    else:
        return a == b


class LookupTableCompiler:
    @staticmethod
    def compile_cv(lut: LookupTableImpl, cv: dict[str, list[str]] | None) -> dict[str, list[str]]:
        if cv is not None:
            lut["cv"] = cv

    @staticmethod
    def compile_cf(lut: LookupTableImpl, cf: rulebook_model.LUCF | None, ds: netCDF4.Dataset) -> dict[str, typing.Any]:
        if cf is not None:
            lut["cf"] = {}
            if cf.axis:
                lut["cf"]["axis"] = {}
                # Axis names.
                # TODO: This may need to be made more robust.
                #       It relies on coordinate variables having the 'axis'
                #       attribute, which formally is not a 'must'.
                #
                axis_variables = cfutil.get_axis_variables(ds)
                axis_method_mapping = {
                    "T": cfutil.get_time_variables,
                    "Z": cfutil.get_z_variables,
                    "Y": cfutil.get_latitude_variables,
                    "X": cfutil.get_longitude_variables,
                }
                for axis in cf.axis:
                    try:
                        lut["cf"]["axis"][axis.value] = set(axis_method_mapping[axis.value](ds)).intersection(axis_variables).pop()
                    except Exception as e:
                        raise Exception(f"Failed to get name for '{axis.value}' axis, {e}") from e

    @staticmethod
    def compile_cmip(lut: LookupTableImpl, cmip: rulebook_model.LUCMIP | None, ds: netCDF4.Dataset) -> dict[str, typing.Any]:
        if cmip is not None:
            lut["cmip"] = {}
            if cmip.path_drs or cmip.file_drs:
                try:
                    path_elements, file_elements = cmiputil.extract_drs_elements(
                        pathlib.Path(ds.filepath()),
                        path_drs=cmip.path_drs,
                        file_drs=cmip.file_drs,
                    )
                    lut["cmip"]["path_drs"] = path_elements
                    lut["cmip"]["file_drs"] = file_elements
                except Exception as e:
                    raise Exception(f"Failed to extract DRS elements, {e}") from e
            if cmip.time is not None:
                lut["cmip"]["time"] = {}
                try:
                    var = ds.variables[lut.lookup(cmip.time.variable)]
                    lut["cmip"]["time"]["count"] = cmiputil.time_range_to_expected_point_count(
                        lut.lookup(cmip.time.range),
                        lut.lookup(cmip.time.frequency),
                        var.calendar,
                    )
                except Exception as e:
                    raise Exception(f"Failed to calculate expected data points along time dimension: {e}") from e


class LookupTableImpl(dict):
    def lookup(self, key: str | rulebook_model.Lookup) -> typing.Any:
        if isinstance(key, rulebook_model.Lookup):
            try:
                keys = key.lookup.split(".")
                value = self
                for k in keys:
                    value = value[k]
                return value
            except Exception as e:
                raise KeyError(f"Lookup failed for '{key.lookup}', {e}") from e
        else:
            return key


class RuleValidator:
    @staticmethod
    def validate_rule_section(
        ds: netCDF4.Dataset,
        rc: rulebook_model.RuleSection,
        lut: LookupTableImpl,
    ) -> list[Result]:
        rules_result_list = RuleValidator.validate_rule_or_rule_list(ds, rc.rules, lut)
        logic_result, logic_message = RuleValidator.apply_rule_list_logic(rules_result_list, rulebook_model.ERuleListLogic.ALL)
        return [
            Result(
                BaseCheck.LOW if logic_result else BaseCheck.HIGH,
                logic_result,
                name=[f"§{rc.section} {rc.heading}"],
                msgs=None if logic_result else [logic_message],
                children=rules_result_list,
            )
        ]

    @staticmethod
    def validate_rule_or_rule_list(
        ds: netCDF4.Dataset | netCDF4.Variable,
        rules: rulebook_model.RuleUnion | rulebook_model.RuleUnionList,
        lut: LookupTableImpl,
    ) -> list[Result]:
        if not isinstance(rules, list):
            rules = [rules]

        rules_result_list = []
        for rule in rules:
            if isinstance(rule, rulebook_model.FileFormatRule):
                rules_result_list.extend(RuleValidator.validate_format(ds, rule, lut))
            elif isinstance(rule, rulebook_model.DimensionRule):
                rules_result_list.extend(RuleValidator.validate_dimension(ds, rule, lut))
            elif isinstance(rule, rulebook_model.AttributeRule):
                rules_result_list.extend(RuleValidator.validate_attribute(ds, rule, lut))
            elif isinstance(rule, rulebook_model.VariableRule):
                rules_result_list.extend(RuleValidator.validate_variable(ds, rule, lut))
            elif isinstance(rule, rulebook_model.DataRule):
                rules_result_list.extend(RuleValidator.validate_variable_data(ds, rule, lut))
            elif isinstance(rule, rulebook_model.ConditionalRule):
                rules_result_list.extend(RuleValidator.validate_conditional(ds, rule, lut))
            elif isinstance(rule, rulebook_model.RuleListLogicRule):
                rules_result_list.extend(RuleValidator.validate_rule_list_logic(ds, rule, lut))
        return rules_result_list

    @staticmethod
    def validate_format(
        ds: netCDF4.Dataset,
        r: rulebook_model.FileFormatRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        ctx.assert_true(ds.data_model == r.data_model, f"Data model is '{ds.data_model}' but must be '{r.data_model}'.")
        result = ctx.to_result()
        if result_is_success(result):
            result.msgs.append("Format rule met.")
        return [result]

    @staticmethod
    def validate_dimension(
        ds: netCDF4.Dataset,
        r: rulebook_model.DimensionRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        results = []
        rule: rulebook_model.DimensionRule
        for rule in RuleValidator.expand_rule("dimension", r, lut):
            dimension_name = lut.lookup(rule.dimension)
            ctx = TestCtx(BaseCheck.HIGH, messages=[rule.description] if rule.description else None)
            try:
                dimension = ds.dimensions[dimension_name]
            except KeyError:
                ctx.assert_true(
                    not rule.required,
                    f"Dimension '{dimension_name}' is required but missing.",
                )
            else:
                ctx.assert_true(
                    rule.size == 0 or rule.size == dimension.size,
                    f"Dimension '{dimension_name}' has size {dimension.size} but must be {rule.size}.",
                )
            result = ctx.to_result()
            if result_is_success(result):
                result.msgs.append(f"Dimension '{dimension_name}' meets specified rules.")
            results.append(result)
        return results

    @staticmethod
    def validate_attribute(
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.AttributeRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        results = []
        rule: rulebook_model.AttributeRule
        for rule in RuleValidator.expand_rule("attribute", r, lut):
            attribute_name = lut.lookup(rule.attribute)
            ctx = TestCtx(BaseCheck.HIGH, messages=[rule.description] if rule.description else None)
            try:
                value = lut.lookup(ds.getncattr(attribute_name))
            except AttributeError:
                ctx.assert_true(
                    not rule.required,
                    f"Attribute '{attribute_name}' is required but missing.",
                )
            else:
                if rule.must_equal is not None:
                    must_equal = lut.lookup(rule.must_equal)
                    ctx.assert_true(
                        equal_or_equal_to_precision(value, must_equal),
                        f"Attribute '{attribute_name}' has value '{value}' but must equal '{must_equal}'.",
                    )
                elif rule.allowed_values is not None:
                    allowed_values = [lut.lookup(v) for v in lut.lookup(rule.allowed_values)]
                    ctx.assert_true(
                        value in allowed_values,
                        f"Attribute '{attribute_name}' has value '{value}' but must be one of {allowed_values}.",
                    )
                elif rule.pattern is not None:
                    pattern = lut.lookup(rule.pattern)
                    ctx.assert_true(
                        re.search(pattern, value),
                        f"Attribute '{attribute_name}' has value '{value}' which does not match the pattern '{pattern}'.",
                    )
            result = ctx.to_result()
            if result_is_success(result):
                result.msgs.append(f"Attribute '{attribute_name}' meets specified rules.")
            results.append(result)
        return results

    @staticmethod
    def validate_variable(
        var: netCDF4.Variable,
        r: rulebook_model.VariableRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        results = []
        rule: rulebook_model.VariableRule
        for rule in RuleValidator.expand_rule("variable", r, lut):
            variable_name = lut.lookup(rule.variable)
            ctx = TestCtx(BaseCheck.HIGH, variable=variable_name, messages=[rule.description] if rule.description else None)
            rules_result_list = []
            try:
                variable = var.variables[variable_name]
            except KeyError:
                ctx.assert_true(
                    not rule.required,
                    f"Variable '{variable_name}' is required but missing.",
                )
            else:
                if rule.dimensions is not None:
                    dimensions = tuple([lut.lookup(d) for d in rule.dimensions])
                    ctx.assert_true(
                        variable.dimensions == dimensions,
                        f"Variable '{variable_name}' has dimensions {variable.dimensions}, must be {dimensions}.",
                    )
                filters = variable.filters()
                if rule.compression_type != rulebook_model.ECompressionType.UNSPECIFIED:
                    var_compression_type = rulebook_model.ECompressionType.NONE
                    for t in rulebook_model.ECompressionType:
                        if t not in [rulebook_model.ECompressionType.UNSPECIFIED, rulebook_model.ECompressionType.NONE] and filters[t.value]:
                            var_compression_type = t.value
                            break
                    ctx.assert_true(
                        var_compression_type == rule.compression_type.value,
                        f"Variable '{variable_name}' has compression type '{var_compression_type}', must be '{rule.compression_type.value}'.",
                    )
                if rule.compression_level is not None:
                    ctx.assert_true(
                        filters["complevel"] == rule.compression_level,
                        f"Variable '{variable_name}' has compression level {filters['complevel']}, must be {rule.compression_level}.",
                    )

                variable_rules = rule.rules if isinstance(rule.rules, list) else [rule.rules]
                if len(variable_rules) > 0:
                    rules_result_list = RuleValidator.validate_rule_or_rule_list(variable, variable_rules, lut)
                    logic_result, logic_message = RuleValidator.apply_rule_list_logic(rules_result_list, rulebook_model.ERuleListLogic.ALL)
                    ctx.assert_true(logic_result, logic_message)

            result = ctx.to_result()
            result.children = rules_result_list
            if result_is_success(result):
                result.msgs.append(f"Variable '{variable_name}' meets specified rules.")
            else:
                result.msgs.insert(0, f"Variable '{variable_name}' has issues.")
            results.append(result)
        return results

    @staticmethod
    def validate_variable_data(
        var: netCDF4.Variable,
        r: rulebook_model.DataRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        ctx.assert_true(
            var.dtype.name == r.dtype,
            f"Data has dtype '{var.dtype.name}' but must be '{r.dtype}'.",
        )
        ctx.assert_true(
            var.dtype.byteorder == r.byteorder.value,
            f"Data has byteorder '{var.dtype.byteorder}' but must be '{r.byteorder.value}' ({r.byteorder}).",
        )
        if r.shape is not None:
            shape = tuple([int(lut.lookup(s)) for s in r.shape])
            ctx.assert_true(
                var.shape == shape,
                f"Data has shape '{var.shape}' but must be '{shape}'.",
            )
        if r.monotonicity is not None:
            if len(var.shape) != 1:
                ctx.add_failure(f"Data has shape '{var.shape}' but must be one-dimensional to determine monotonicity.")
            else:
                operator = {
                    rulebook_model.EMonotonicity.INCREASING: np.less_equal,
                    rulebook_model.EMonotonicity.STRICTLY_INCREASING: np.less,
                    rulebook_model.EMonotonicity.DECREASING: np.greater_equal,
                    rulebook_model.EMonotonicity.STRICTLY_DECREASING: np.greater,
                }
                var_data = var[:]
                ctx.assert_true(
                    np.all(operator[r.monotonicity](var_data[:-1], var_data[1:])),
                    f"Data does not fulfil monotonicity rule '{r.monotonicity.value}'.",
                )
        if r.min is not None or r.max is not None:
            var_data = var[:]
            if r.min is not None:
                var_data_min = np.min(var_data)
                ctx.assert_true(r.min <= var_data_min, f"Minimum of data is {var_data_min}, minimum allowed value is {r.min}, ")
            if r.max is not None:
                var_data_max = np.max(var_data)
                ctx.assert_true(r.max >= var_data_max, f"Maximum of data is {var_data_max}, maximum allowed value is {r.max}, ")

        result = ctx.to_result()
        if result_is_success(result):
            result.msgs.append(f"Data of variable '{lut.lookup(var.name)}' meets specified rules.")
        return [result]

    @staticmethod
    def validate_conditional(
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.ConditionalRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        dependent_result_list = []

        condition_result_list = RuleValidator.validate_rule_or_rule_list(ds, r.condition, lut)
        logic_result, _ = RuleValidator.apply_rule_list_logic(condition_result_list, rulebook_model.ERuleListLogic.ALL)
        if logic_result:
            dependent_result_list = RuleValidator.validate_rule_or_rule_list(ds, r.dependent, lut)
            logic_result, logic_message = RuleValidator.apply_rule_list_logic(dependent_result_list, rulebook_model.ERuleListLogic.ALL)
            ctx.assert_true(logic_result, "Checking dependent rules: " + logic_message)

        result = ctx.to_result()
        result.children = dependent_result_list
        if result_is_success(result):
            result.msgs.append("Conditional rule met.")
        return [result]

    @staticmethod
    def validate_rule_list_logic(
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.RuleListLogicRule,
        lut: LookupTableImpl,
    ) -> list[Result]:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)

        rules_result_list = RuleValidator.validate_rule_or_rule_list(ds, r.rules, lut)
        logic_result, logic_message = RuleValidator.apply_rule_list_logic(rules_result_list, r.logic)
        ctx.assert_true(logic_result, logic_message)

        result = ctx.to_result()
        result.children = rules_result_list
        return [result]

    @staticmethod
    def expand_rule(
        expanding_field_name: str,
        r: rulebook_model.RuleBaseModel,
        lut: LookupTableImpl,
    ) -> list[Result]:
        expanding_field_value = lut.lookup(getattr(r, expanding_field_name))
        if isinstance(expanding_field_value, list):
            return [r.model_copy(update={expanding_field_name: v}) for v in expanding_field_value]
        else:
            return [r]

    @staticmethod
    def apply_rule_list_logic(
        results: list[Result],
        logic: rulebook_model.ERuleListLogic,
    ) -> tuple[bool, str]:
        validations_ok = [node.value[0] == node.value[1] for node in results]
        score = sum(validations_ok)
        total = len(validations_ok)
        if logic == rulebook_model.ERuleListLogic.ALL:
            if not all(validations_ok):
                return (False, f"All rules must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "All rules are met.")

        elif logic == rulebook_model.ERuleListLogic.EXACTLY_ONE:
            if sum(validations_ok) != 1:
                return (False, f"Exactly one (one and only one) rule must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "Exactly one rule is met.")

        elif logic == rulebook_model.ERuleListLogic.AT_LEAST_ONE:
            if not any(validations_ok):
                return (False, f"At least one rule must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "At least one rule is met.")

        else:  # if logic == rulebook_model.RuleListLogic.NONE:
            if any(validations_ok):
                return (False, f"No rules must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "No rules are met.")


class RuleBookImpl:
    def __init__(self, rulebook: dict[str, typing.Any]) -> None:
        self._rulebook = rulebook_model.RuleBookModel.model_validate(rulebook)
        self._lut = {}

    @staticmethod
    def from_str(rulebook_str: str) -> RuleBookImpl:
        rulebook_dict = yaml.safe_load(rulebook_str)
        return RuleBookImpl(rulebook_dict)

    @staticmethod
    def from_file(rulebook_file: pathlib.Path | str) -> RuleBookImpl:
        with open(rulebook_file) as f:
            return RuleBookImpl.from_str(f.read())

    def validate(self, ds: netCDF4.Dataset) -> list[Result]:
        colorama.init()
        lut = LookupTableImpl()
        if self._rulebook.lookup_table:
            try:
                LookupTableCompiler.compile_cv(lut, self._rulebook.lookup_table.cv)
                LookupTableCompiler.compile_cf(lut, self._rulebook.lookup_table.cf, ds)
                LookupTableCompiler.compile_cmip(lut, self._rulebook.lookup_table.cmip, ds)
            except Exception as e:
                return [Result(BaseCheck.HIGH, False, msgs=[f"While building lookup table (cf): {e}"])]

        results = []
        for rule_section in self._rulebook.rule_sections:
            section_results = RuleValidator.validate_rule_section(ds, rule_section, lut)
            for section_result in section_results:
                section_result.msgs = [self._flatten_result_tree(section_result)]  # Assign single hierarchical error message
                section_result.children = None  # Disconnect children
            results.extend(section_results)
        return results

    def _flatten_result_tree(self, result, indent=0) -> str:
        #
        # TODO: This is a temporary solution with some formatting magic.
        #       Formatting should be taken care of outside of the checker.
        #
        indent_string = "\n" + "  " * (indent + 1)
        err = colorama.Fore.GREEN + "\u2714 " if result_is_success(result) else colorama.Fore.RED + "\u2716 "
        level_msg = (indent_string if indent > 0 else "") + err + (indent_string + "  ").join(result.msgs)
        if not result_is_success(result):
            for child in result.children:
                level_msg = level_msg + self._flatten_result_tree(child, indent + 1)
        return level_msg + colorama.Style.RESET_ALL
