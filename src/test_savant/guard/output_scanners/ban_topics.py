from pydantic import confloat
from typing import Literal, Optional, Sequence
from ..input_scanners.base_scanner import Scanner, ScannerResult

class BanTopics(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["small", "base", "large"]
    topics: Optional[list[str]] = None
    result: Optional[ScannerResult] = None