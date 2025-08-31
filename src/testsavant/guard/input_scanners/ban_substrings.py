from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class BanSubstrings(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    substrings: Optional[list[str]] = None
    tag: Literal["default"] = "default"
    case_sensitive: Optional[bool] = None
    redact: Optional[bool] = None
    contains_all: Optional[bool] = None
    result: Optional[ScannerResult] = None