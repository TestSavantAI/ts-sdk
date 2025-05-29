from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class InvisibleText(Scanner):
    tag: Literal["default"] = "default"
    result: Optional[ScannerResult] = None
