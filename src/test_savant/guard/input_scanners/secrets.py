from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class Secrets(Scanner):
    tag: Literal["default"] = "default"
    redact_mode: Optional[Literal["partial", "all", "hash"]] = None
    result: Optional[ScannerResult] = None