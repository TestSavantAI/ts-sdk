from pydantic import confloat
from typing import Literal, Optional, Sequence
from .base_scanner import Scanner, ScannerResult

class Code(Scanner):
    threshold: confloat(ge=0.0, le=1.0) = 0.6
    tag: Literal["base"]
    languages: list[str]
    is_blocked: bool = True
    result: Optional[ScannerResult] = None
