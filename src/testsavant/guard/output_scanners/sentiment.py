from pydantic import confloat
from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class Sentiment(Scanner):
    tag: Literal["default"] = "default"
    threshold: Optional[confloat(ge=-1, le=1.0)] = None
    result: Optional[ScannerResult] = None