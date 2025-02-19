from compliance_checker.base import BaseCheck, TestCtx
from compliance_checker.qctable.qctable_base import QCTableBaseCheck


class QCTableCordexCmip6Check(QCTableBaseCheck):
    """Test class for cordex-cmip6 checks from QC table."""

    register_checker = True
    _cc_spec = "qctable_cordex_cmip6"
    _cc_spec_version = "1.0"
    _cc_description = "QCTable"
    _cc_url = ""
    _cc_display_headers = {3: "Errors", 2: "Warnings", 1: "Info"}

    def __init__(self, options=None):  # initialize with parent methods and data
        super().__init__(options)

    def check_attributes(self, ds):
        ctx: TestCtx = self.get_test_ctx(BaseCheck.HIGH, "Mandatory attributes")
        if self._check_A001(ds, ctx):
            self._check_A002(ds, ctx)
        if self._check_A023(ds, ctx):
            self._check_A024(ds, ctx)
            self._check_A026(ds, ctx)
        return ctx.to_result()

    def check_dimensions(self, ds):
        ctx: TestCtx = self.get_test_ctx(BaseCheck.HIGH, "Mandatory dimensions")
        if self._check_D001(ds, ctx):
            self._check_D003(ds, ctx)
        if self._check_D010(ds, ctx):
            self._check_D012(ds, ctx)
        if self._check_D016(ds, ctx):
            self._check_D018(ds, ctx)
        return ctx.to_result()
