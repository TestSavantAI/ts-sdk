from pydantic import confloat
from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class TokenLimit(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: Literal["default"] = "default"
    limit: Optional[int] = None
    result: Optional[ScannerResult] = None