from pydantic import confloat
from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class Sentiment(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: Literal["default"] = "default"
    threshold: Optional[confloat(ge=-1, le=1.0)] = None
    result: Optional[ScannerResult] = None