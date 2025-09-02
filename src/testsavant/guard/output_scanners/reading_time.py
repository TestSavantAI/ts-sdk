from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult
import json

class ReadingTime(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    max_time: Optional[float] = None
    truncate: Optional[bool] = None
    tag: Literal["default"] = "default"
    result: Optional[ScannerResult] = None