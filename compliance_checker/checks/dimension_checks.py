import typing

from compliance_checker.base import BaseCheck, Result
from compliance_checker.checks.common import SEVERITY_STR, msg_prefix


def check_dimension_exists(
    ds: typing.Any,
    dimension: str,
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
):
    return Result(
        severity,
        dimension in ds.dimensions,
        msgs=[msg_prefix(check_id) + f"Dimension '{dimension}' {SEVERITY_STR[severity]} exist"],
    )


def check_dimension_size(
    ds: typing.Any,
    dimension: str,
    size: int | str,
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
):
    try:
        if size == "unlimited":
            return Result(
                severity,
                ds.dimensions[dimension].isunlimited(),
                msgs=[msg_prefix(check_id) + f"Dimension '{dimension}' {SEVERITY_STR[severity]} be unlimited"],
            )
        elif size == "positive":
            return Result(
                severity,
                ds.dimensions[dimension].size > 0,
                msgs=[msg_prefix(check_id) + f"Dimension '{dimension}' {SEVERITY_STR[severity]} be positive non-zero"],
            )
        else:
            return Result(
                severity,
                ds.dimensions[dimension].size == size,
                msgs=[msg_prefix(check_id) + f"Dimension '{dimension}' {SEVERITY_STR[severity]} have size {size}"],
            )
    except KeyError:
        return Result(
            severity,
            False,
            msgs=[msg_prefix(check_id) + f"Dimension '{dimension}' must exist to have a size"],
        )
