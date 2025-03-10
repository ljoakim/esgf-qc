from __future__ import annotations

import pathlib
import re
import typing

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


class RuleBook:
    def __init__(self, rulebook: str) -> None:
        self._rulebook = rulebook_model.RuleBookModel.model_validate(rulebook)
        self._lookup_table = {}

    @staticmethod
    def from_file(rulebook_file: pathlib.Path | str) -> RuleBook:
        with open(rulebook_file) as f:
            rulebook_str = yaml.safe_load(f)
            return RuleBook(rulebook_str)

    def validate(self, ds: netCDF4.Dataset) -> list[Result]:
        results = []
        if self._rulebook.lookup_table:
            self._lookup_table, result = self._rebuild_lookup_table(ds)
            if not result_is_success(result):
                return [result]
        for rule_section in self._rulebook.rule_sections:
            result = self._apply_rule_section(ds, rule_section)
            result.msgs = [self._flatten_result_tree(result)]  # Assign single hierarchical error message
            result.children = None  # Disconnect children
            results.append(result)
        return results

    def _flatten_result_tree(self, result, indent=0) -> str:
        #
        # TODO: This is a temporary solution with some formatting magic.
        #       Formatting should be taken care of outside of the checker.
        #
        indent_string = "\n" + "  " * (indent + 1)
        err = "\u2714 " if result_is_success(result) else "\u2716 "
        level_msg = (indent_string if indent > 0 else "") + err + (indent_string + "  ").join(result.msgs)
        if not result_is_success(result):
            for child in result.children:
                level_msg = level_msg + self._flatten_result_tree(child, indent + 1)
        return level_msg

    def _rebuild_lookup_table(self, ds: netCDF4.Dataset) -> tuple[dict[str, typing.Any], Result]:
        ctx = TestCtx(BaseCheck.HIGH, "Building lookup table")
        lookup_table = {}

        # CV table
        #
        if self._rulebook.lookup_table.cv is not None:
            lookup_table["cv"] = self._rulebook.lookup_table.cv

        # CF table
        #
        if self._rulebook.lookup_table.cf is not None:
            lookup_table["cf"] = {}
            if self._rulebook.lookup_table.cf.axis:
                # Axis names.
                # TODO: This probably needs to be made more robust.
                #       It relies on coordinate variables having the 'axis' attribute,
                #       which formally is not a 'must'.
                #
                lookup_table["cf"]["axis"] = {}
                axis_variables = cfutil.get_axis_variables(ds)
                axis_method_mapping = {
                    "T": cfutil.get_time_variables,
                    "Z": cfutil.get_z_variables,
                    "Y": cfutil.get_latitude_variables,
                    "X": cfutil.get_longitude_variables,
                }
                for axis in self._rulebook.lookup_table.cf.axis:
                    try:
                        lookup_table["cf"]["axis"][axis.value] = set(axis_method_mapping[axis.value](ds)).intersection(axis_variables).pop()
                    except Exception:
                        ctx.add_failure(f"While building lookup table (cf.axis): Failed to get name for '{axis.value}' axis.")

        # CMIP table
        #
        if self._rulebook.lookup_table.cmip is not None:
            lookup_table["cmip"] = {}
            if self._rulebook.lookup_table.cmip.path_drs or self._rulebook.lookup_table.cmip.file_drs:
                try:
                    path_elements, file_elements = cmiputil.extract_drs_elements(
                        pathlib.Path(ds.filepath()),
                        path_drs=self._rulebook.lookup_table.cmip.path_drs,
                        file_drs=self._rulebook.lookup_table.cmip.file_drs,
                    )
                    lookup_table["cmip"]["path_drs"] = path_elements
                    lookup_table["cmip"]["file_drs"] = file_elements
                except Exception as e:
                    ctx.add_failure(f"While building lookup table (cmip.path_drs, cmip.file_drs): {e}")
            if self._rulebook.lookup_table.cmip.time is not None:
                lookup_table["cmip"]["time"] = {}
                try:
                    var = ds.variables[self._lookup(self._rulebook.lookup_table.cmip.time.variable, lookup_table)]
                    lookup_table["cmip"]["time"]["count"] = cmiputil.time_range_to_expected_point_count(
                        self._lookup(self._rulebook.lookup_table.cmip.time.range, lookup_table),
                        self._lookup(self._rulebook.lookup_table.cmip.time.frequency, lookup_table),
                        var.calendar,
                    )
                except Exception as e:
                    ctx.add_failure(f"While building lookup table (cmip.time): {e}")

        return lookup_table, ctx.to_result()

    def _lookup(self, key: typing.Any, table: dict[str, typing.Any] | None = None) -> typing.Any:
        if isinstance(key, rulebook_model.Lookup):
            try:
                keys = key.lookup.split(".")
                value = self._lookup_table if table is None else table
                for k in keys:
                    value = value[k]
                return value
            except (AttributeError, KeyError):
                return key
        else:
            return key

    def _apply_rule_section(
        self,
        ds: netCDF4.Dataset,
        rc: rulebook_model.RuleSection,
    ) -> Result:
        rules_result_list = self._apply_rule_or_rule_list(ds, rc.rules)
        logic_result, logic_message = self._rule_list_logic(rules_result_list, rulebook_model.RuleListLogic.ALL)
        return Result(
            BaseCheck.LOW if logic_result else BaseCheck.HIGH,
            logic_result,
            name=[f"§{rc.section} {rc.heading}"],
            msgs=None if logic_result else [logic_message],
            children=rules_result_list,
        )

    def _apply_rule_or_rule_list(
        self,
        ds: netCDF4.Dataset | netCDF4.Variable,
        rules: rulebook_model.RuleUnionList,
    ) -> list[Result]:
        if not isinstance(rules, list):
            rules = [rules]

        rules_result_list = []
        for rule in rules:
            if isinstance(rule, rulebook_model.FileFormatRule):
                rules_result_list.append(self._apply_format_rule(ds, rule))
            elif isinstance(rule, rulebook_model.DimensionRule):
                rules_result_list.extend(self._expand_and_apply_dimension_rule(ds, rule))
            elif isinstance(rule, rulebook_model.AttributeRule):
                rules_result_list.extend(self._expand_and_apply_attribute_rule(ds, rule))
            elif isinstance(rule, rulebook_model.VariableRule):
                rules_result_list.extend(self._expand_and_apply_variable_rule(ds, rule))
            elif isinstance(rule, rulebook_model.DataRule):
                rules_result_list.append(self._apply_variable_data_rule(ds, rule))
            elif isinstance(rule, rulebook_model.ConditionalRule):
                rules_result_list.append(self._apply_conditional_rule(ds, rule))
            elif isinstance(rule, rulebook_model.RuleListLogicRule):
                rules_result_list.append(self._apply_rule_list_logic_rule(ds, rule))
        return rules_result_list

    def _apply_format_rule(
        self,
        ds: netCDF4.Dataset,
        r: rulebook_model.FileFormatRule,
    ) -> Result:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        ctx.assert_true(ds.data_model == r.data_model, f"Data model is '{ds.data_model}' but must be '{r.data_model}'.")
        result = ctx.to_result()
        if result_is_success(result):
            result.msgs.append("Format rule met.")
        return result

    def _expand_and_apply_dimension_rule(
        self,
        ds: netCDF4.Dataset,
        r: rulebook_model.DimensionRule,
    ) -> list[Result]:
        dimension_name = self._lookup(r.dimension)
        if isinstance(dimension_name, list):
            rules = [r.model_copy(update={"dimension": d}) for d in dimension_name]
        else:
            rules = [r]
        return [self._apply_dimension_rule(ds, rule) for rule in rules]

    def _apply_dimension_rule(
        self,
        ds: netCDF4.Dataset,
        r: rulebook_model.DimensionRule,
    ) -> Result:
        dimension_name = self._lookup(r.dimension)
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        try:
            dimension = ds.dimensions[dimension_name]
        except KeyError:
            ctx.assert_true(
                not r.required,
                f"Dimension '{dimension_name}' is required but missing.",
            )
        else:
            ctx.assert_true(
                r.size == 0 or r.size == dimension.size,
                f"Dimension '{dimension_name}' has size {dimension.size} but must be {r.size}.",
            )
        result = ctx.to_result()
        if result_is_success(result):
            result.msgs.append(f"Dimension '{dimension_name}' meets specified rules.")
        return result

    def _expand_and_apply_attribute_rule(
        self,
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.AttributeRule,
    ) -> list[Result]:
        attribute_name = self._lookup(r.attribute)
        if isinstance(attribute_name, list):
            rules = [r.model_copy(update={"attribute": v}) for v in attribute_name]
        else:
            rules = [r]
        return [self._apply_attribute_rule(ds, rule) for rule in rules]

    def _apply_attribute_rule(
        self,
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.AttributeRule,
    ) -> Result:
        attribute_name = self._lookup(r.attribute)
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        try:
            value = self._lookup(ds.getncattr(attribute_name))
        except AttributeError:
            ctx.assert_true(
                not r.required,
                f"Attribute '{attribute_name}' is required but missing.",
            )
        else:
            if r.must_equal is not None:
                must_equal = self._lookup(r.must_equal)
                ctx.assert_true(
                    self._equal_or_equal_to_precision(value, must_equal),
                    f"Attribute '{attribute_name}' has value '{value}' but must equal '{must_equal}'.",
                )
            elif r.allowed_values is not None:
                allowed_values = [self._lookup(v) for v in self._lookup(r.allowed_values)]
                ctx.assert_true(
                    value in allowed_values,
                    f"Attribute '{attribute_name}' has value '{value}' but must be one of {allowed_values}.",
                )
            elif r.pattern is not None:
                pattern = self._lookup(r.pattern)
                ctx.assert_true(
                    re.search(pattern, value),
                    f"Attribute '{attribute_name}' has value '{value}' which does not match the pattern '{pattern}'.",
                )
        result = ctx.to_result()
        if result_is_success(result):
            result.msgs.append(f"Attribute '{attribute_name}' meets specified rules.")
        return result

    def _expand_and_apply_variable_rule(
        self,
        var: netCDF4.Variable,
        r: rulebook_model.VariableRule,
    ) -> list[Result]:
        variable_name = self._lookup(r.variable)
        if isinstance(variable_name, list):
            rules = [r.model_copy(update={"variable": v}) for v in variable_name]
        else:
            rules = [r]
        return [self._apply_variable_rule(var, rule) for rule in rules]

    def _apply_variable_rule(
        self,
        var: netCDF4.Variable,
        r: rulebook_model.VariableRule,
    ) -> Result:
        variable_name = self._lookup(r.variable)
        ctx = TestCtx(BaseCheck.HIGH, variable=variable_name, messages=[r.description] if r.description else None)
        rules_result_list = []
        try:
            variable = var.variables[variable_name]
        except KeyError:
            ctx.assert_true(
                not r.required,
                f"Variable '{variable_name}' is required but missing.",
            )
        else:
            if r.dimensions is not None:
                dimensions = tuple([self._lookup(d) for d in r.dimensions])
                ctx.assert_true(
                    variable.dimensions == dimensions,
                    f"Variable '{variable_name}' has dimensions {variable.dimensions}, must be {dimensions}.",
                )
            filters = variable.filters()
            if r.compression_type != rulebook_model.CompressionType.UNSPECIFIED:
                var_compression_type = rulebook_model.CompressionType.NONE
                for t in rulebook_model.CompressionType:
                    if t not in [rulebook_model.CompressionType.UNSPECIFIED, rulebook_model.CompressionType.NONE] and filters[t.value]:
                        var_compression_type = t.value
                        break
                ctx.assert_true(
                    var_compression_type == r.compression_type.value,
                    f"Variable '{variable_name}' has compression type '{var_compression_type}', must be '{r.compression_type.value}'.",
                )
            if r.compression_level is not None:
                ctx.assert_true(
                    filters["complevel"] == r.compression_level,
                    f"Variable '{variable_name}' has compression level {filters['complevel']}, must be {r.compression_level}.",
                )

            rules = r.rules if isinstance(r.rules, list) else [r.rules]
            if len(rules) > 0:
                rules_result_list = self._apply_rule_or_rule_list(variable, rules)
                logic_result, logic_message = self._rule_list_logic(rules_result_list, rulebook_model.RuleListLogic.ALL)
                ctx.assert_true(logic_result, logic_message)

        result = ctx.to_result()
        result.children = rules_result_list
        if result_is_success(result):
            result.msgs.append(f"Variable '{variable_name}' meets specified rules.")
        else:
            result.msgs.insert(0, f"Variable '{variable_name}' has issues.")
        return result

    def _apply_variable_data_rule(
        self,
        var: netCDF4.Variable,
        r: rulebook_model.DataRule,
    ) -> Result:
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
            shape = tuple([int(self._lookup(s)) for s in r.shape])
            ctx.assert_true(
                var.shape == shape,
                f"Data has shape '{var.shape}' but must be '{shape}'.",
            )
        if r.monotonicity is not None:
            if len(var.shape) != 1:
                ctx.add_failure(f"Data has shape '{var.shape}' but must be one-dimensional to determine monotonicity.")
            else:
                operator = {
                    rulebook_model.Monotonicity.INCREASING: np.less_equal,
                    rulebook_model.Monotonicity.STRICTLY_INCREASING: np.less,
                    rulebook_model.Monotonicity.DECREASING: np.greater_equal,
                    rulebook_model.Monotonicity.STRICTLY_DECREASING: np.greater,
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
            result.msgs.append(f"Data of variable '{self._lookup(var.name)}' meets specified rules.")
        return result

    def _apply_conditional_rule(
        self,
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.ConditionalRule,
    ) -> Result:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)
        dependent_result_list = []

        condition_result_list = self._apply_rule_or_rule_list(ds, r.condition)
        logic_result, _ = self._rule_list_logic(condition_result_list, rulebook_model.RuleListLogic.ALL)
        if logic_result:
            dependent_result_list = self._apply_rule_or_rule_list(ds, r.dependent)
            logic_result, logic_message = self._rule_list_logic(dependent_result_list, rulebook_model.RuleListLogic.ALL)
            ctx.assert_true(logic_result, "Checking dependent rules: " + logic_message)

        result = ctx.to_result()
        result.children = dependent_result_list
        if result_is_success(result):
            result.msgs.append("Conditional rule met.")
        return result

    def _apply_rule_list_logic_rule(
        self,
        ds: netCDF4.Dataset | netCDF4.Variable,
        r: rulebook_model.RuleListLogicRule,
    ) -> list[Result]:
        ctx = TestCtx(BaseCheck.HIGH, messages=[r.description] if r.description else None)

        rules_result_list = self._apply_rule_or_rule_list(ds, r.rules)
        logic_result, logic_message = self._rule_list_logic(rules_result_list, r.logic)
        ctx.assert_true(logic_result, logic_message)

        result = ctx.to_result()
        result.children = rules_result_list
        return result

    def _rule_list_logic(
        self,
        validation_nodes: list[Result],
        logic: rulebook_model.RuleListLogic,
    ) -> tuple[bool, str]:
        validations_ok = [node.value[0] == node.value[1] for node in validation_nodes]
        score = sum(validations_ok)
        total = len(validations_ok)
        if logic == rulebook_model.RuleListLogic.ALL:
            if not all(validations_ok):
                return (False, f"All rules must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "All rules are met.")

        elif logic == rulebook_model.RuleListLogic.EXACTLY_ONE:
            if sum(validations_ok) != 1:
                return (False, f"Exactly one (one and only one) rule must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "Exactly one rule is met.")

        elif logic == rulebook_model.RuleListLogic.AT_LEAST_ONE:
            if not any(validations_ok):
                return (False, f"At least one rule must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "At least one rule is met.")

        else:  # if logic == rulebook_model.RuleListLogic.NONE:
            if any(validations_ok):
                return (False, f"No rules must be met. Currently {score} out of {total} are met.")
            else:
                return (True, "No rules are met.")

    def _equal_or_equal_to_precision(self, a: typing.Any, b: typing.Any) -> bool:
        float_types = (float, np.float32, np.float64)
        if isinstance(a, float_types) or isinstance(b, float_types):
            if isinstance(a, np.float32):
                return a == np.float32(b)
            else:
                return np.float64(a) == np.float64(b)
        else:
            return a == b
