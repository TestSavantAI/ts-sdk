from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class ReadingTime(Scanner):
    max_time: Optional[float] = None
    truncate: Optional[bool] = None
    tag: Literal["default"] = "default"
    result: Optional[ScannerResult] = None