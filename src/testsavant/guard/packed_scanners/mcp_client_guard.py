from testsavant.guard import OutputPackedGuard
from testsavant.guard.output_scanners import (
    JSON
)

from testsavant.guard.input_scanners import (
    Anonymize
)


class MCPClientGuard(OutputPackedGuard):
    
    def __init__(self, API_KEY=None, PROJECT_ID=None, remote_addr=None, fail_fast=True):
        super().__init__(API_KEY, PROJECT_ID, remote_addr, fail_fast=fail_fast)
        self.add_scanner(JSON(tag="default"))
        self.add_scanner(Anonymize(tag="base", redact=True))