import typing

from compliance_checker.base import BaseCheck, Result
from compliance_checker.checks.common import SEVERITY_STR, msg_prefix


def check_attribute_exists(
    ds: typing.Any,
    attribute: str,
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
):
    return Result(
        severity,
        attribute in ds.ncattrs(),
        msgs=[msg_prefix(check_id) + f"Attribute '{attribute}' {SEVERITY_STR[severity]} exist"],
    )


def check_attribute_type(
    ds: typing.Any,
    attribute: str,
    type_: str,
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
):
    try:
        return Result(
            severity,
            type(ds.getncattr(attribute)) is type_,
            msgs=[msg_prefix(check_id) + f"Attribute '{attribute}' {SEVERITY_STR[severity]} have type {type_}"],
        )
    except AttributeError:
        return Result(
            severity,
            False,
            msgs=[msg_prefix(check_id) + f"Attribute '{attribute}' must exist to have a type"],
        )


def check_attribute_value(
    ds: typing.Any,
    attribute: str,
    value: str | list[str],
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
):
    try:
        a_value = ds.getncattr(attribute)
        return Result(
            severity,
            a_value in value if isinstance(value, list) else a_value == value,
            msgs=[msg_prefix(check_id) + f"Attribute '{attribute}' {SEVERITY_STR[severity]} have value {value}"],
        )
    except AttributeError:
        return Result(
            severity,
            False,
            msgs=[msg_prefix(check_id) + f"Attribute '{attribute}' must exist to have a value"],
        )
