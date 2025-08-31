from pydantic import confloat
from typing import Literal, Optional, Sequence
from .base_scanner import Scanner, ScannerResult

class Code(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    languages: Optional[list[str]] = None
    is_blocked: Optional[bool] = None
    result: Optional[ScannerResult] = None