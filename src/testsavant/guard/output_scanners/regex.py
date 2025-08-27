from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class Regex(Scanner):
    patterns: Optional[list[str]] = None
    tag: Literal["default"] = "default"
    redact: Optional[bool] = None
    is_blocked: Optional[bool] = None
    result: Optional[ScannerResult] = None