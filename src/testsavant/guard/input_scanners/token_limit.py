from pydantic import confloat
from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class TokenLimit(Scanner):
    tag: Literal["default"] = "default"
    limit: Optional[int] = None
    result: Optional[ScannerResult] = None