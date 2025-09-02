from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class Secrets(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: Literal["default"] = "default"
    redact_mode: Optional[Literal["partial", "all", "hash"]] = None
    result: Optional[ScannerResult] = None