from functools import partial

import esgvoc.api as ev
import netCDF4

from compliance_checker.base import BaseCheck, BaseNCCheck, TestCtx
from compliance_checker.checks.attribute_checks import check_attribute_exists, check_attribute_type, check_attribute_value
from compliance_checker.checks.common import CheckListRule, check_list_check, conditional_check, msg_prefix, result_is_success
from compliance_checker.checks.dimension_checks import check_dimension_exists, check_dimension_size


class QCTableBaseCheck(BaseNCCheck, BaseCheck):
    """Test base class for checks from QC table."""

    def __init__(self, options=None):
        super().__init__(options)

    def get_y_coordinate_variable(self, ds: netCDF4.Dataset):
        """Return name of coordinate variable with axis Y."""
        return ds.get_variables_by_attributes(axis="Y")[0].name

    #
    # Just listing the checks for experimenting with different
    # types of checks from the QC table.
    #

    def _check_A001(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """Conventions: Check the existance of the attribute"""
        result = check_attribute_exists(ds, "Conventions", ctx.category, "A001")
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_A002(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """Conventions: Check the type of the attribute is NC_CHAR (in python: str)"""
        result = check_attribute_type(ds, "Conventions", str, ctx.category, "A002")
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_A023(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """activity_id: Check the existance of the attribute"""
        result = check_attribute_exists(ds, "activity_id", ctx.category, "A023")
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_A024(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """activity_id: Check the type of the attribute is NC_CHAR (in python: str)"""
        result = check_attribute_type(ds, "activity_id", str, ctx.category, "A024")
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_A026(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """activity_id: Validate the value against CV terms"""
        #
        # Should be project_id="CORDEX" with mip_era="CMIP6" here (?)
        #
        cv = [term.drs_name for term in ev.get_all_terms_in_collection(project_id="cmip6", collection_id="activity_id")]
        result = check_attribute_value(ds, "activity_id", cv, ctx.category, "A026")
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_D001(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """bnds/axis_nbounds: Check the existence of the dimension"""
        result = check_list_check(
            CheckListRule.EXACTLY_ONE,
            [
                partial(check_dimension_exists, ds, "bnds"),
                partial(check_dimension_exists, ds, "axis_nbounds"),
            ],
            ctx.category,
            "D001",
        )
        return ctx.assert_true(result_is_success(result), result.msgs[0])

    def _check_D003(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """bnds/axis_nbounds: Ensure the value is a positive integer = 2"""
        result = check_list_check(
            CheckListRule.ALL,
            [
                partial(conditional_check, partial(check_dimension_exists, ds, "bnds"), partial(check_dimension_size, ds, "bnds", 2)),
                partial(conditional_check, partial(check_dimension_exists, ds, "axis_nbounds"), partial(check_dimension_size, ds, "axis_nbounds", 2)),
            ],
            ctx.category,
            "D003",
        )
        return ctx.assert_true(result_is_success(result), str(result.msgs[0]))

    def _check_D010(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """rlat: Check the existence of the dimension"""
        try:
            result = check_dimension_exists(ds, self.get_y_coordinate_variable(ds), ctx.category, "D010")
            return ctx.assert_true(result_is_success(result), str(result.msgs[0]))
        except IndexError:
            ctx.add_failure(msg_prefix("D010") + "Failed to find Y dimension")
            return False

    def _check_D012(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """rlat: Ensure the value is a positive integer"""
        try:
            result = check_dimension_size(ds, self.get_y_coordinate_variable(ds), "positive", ctx.category, "D012")
            return ctx.assert_true(result_is_success(result), str(result.msgs[0]))
        except IndexError:
            ctx.add_failure(msg_prefix("D012") + "Failed to find Y dimension")
            return False

    def _check_D016(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """time: Check the existence of the dimension"""
        result = check_dimension_exists(ds, "time", ctx.category, "D016")
        return ctx.assert_true(result_is_success(result), str(result.msgs[0]))

    def _check_D018(self, ds: netCDF4.Dataset, ctx: TestCtx):
        """time: Ensure the value is a positive integer"""
        result = check_dimension_size(ds, "time", "positive", ctx.category, "D018")
        return ctx.assert_true(result_is_success(result), str(result.msgs[0]))
