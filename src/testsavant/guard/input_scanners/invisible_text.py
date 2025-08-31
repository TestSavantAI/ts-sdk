from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class InvisibleText(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: Literal["default"] = "default"
    result: Optional[ScannerResult] = None
