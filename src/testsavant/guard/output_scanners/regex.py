from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class Regex(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    patterns: Optional[list[str]] = None
    tag: Literal["default"] = "default"
    redact: Optional[bool] = None
    is_blocked: Optional[bool] = None
    result: Optional[ScannerResult] = None