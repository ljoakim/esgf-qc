import enum
from collections.abc import Callable

from compliance_checker.base import BaseCheck, Result

SEVERITY_STR = {
    BaseCheck.HIGH: "must",
    BaseCheck.MEDIUM: "should",
    BaseCheck.LOW: "is recommended to",
}


class CheckListRule(enum.Enum):
    ALL = "all"
    EXACTLY_ONE = "exactly one"
    AT_LEAST_ONE = "at least one"
    NONE = "no"


def msg_prefix(prefix: str | None = None) -> str:
    """Generate a prefix string to get common formatting for message prefixes."""
    return f"[{prefix}]: " if prefix is not None else ""


def result_is_success(result: Result) -> bool:
    """Check if a result instance is a complete success."""
    if isinstance(result.value, tuple):
        return result.value[0] == result.value[1]
    return result.value


def check_list_check(
    rule: CheckListRule,
    checks: list[Callable[[], Result]],
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
) -> Result:
    """Check if a list of checks satisfies a CheckListRule condition."""
    results = [c() for c in checks]
    if rule == CheckListRule.ALL:
        rule_success = all(result_is_success(r) for r in results)
    elif rule == CheckListRule.EXACTLY_ONE:
        rule_success = sum([result_is_success(r) for r in results]) == 1
    elif rule == CheckListRule.AT_LEAST_ONE:
        rule_success = any(result_is_success(r) for r in results)
    else:  # rule == CheckListRule.NONE:
        rule_success = not any(result_is_success(r) for r in results)
    msgs = [msg_prefix(check_id) + f"{rule.value.capitalize()} check(s) {SEVERITY_STR[severity]} be valid: {[r.msgs for r in results]}"]
    return Result(severity, rule_success, msgs=msgs)


def conditional_check(
    if_check: Callable[[], Result],
    then_check: Callable[[], Result],
    severity: int = BaseCheck.HIGH,
    check_id: str | None = None,
) -> Result:
    """Conditional check, run consequent check only if first satisfied."""
    if_result = if_check()
    if result_is_success(if_result):
        then_result = then_check()
        then_sucess = result_is_success(then_result)
        msgs = [msg_prefix(check_id) + f"Condition check fulfilled: {if_result.msgs[0]}. Consequent check {SEVERITY_STR[severity]} pass: {then_result.msgs[0]}"]
        return Result(severity, then_sucess, msgs=msgs)
    else:
        return Result(severity, True, msgs=[f"Condition check not fulfilled: {if_result.msgs[0]}. Consequent check not run."])
