from pydantic import confloat
from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class Gibberish(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None