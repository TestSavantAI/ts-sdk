from pydantic import confloat
from typing import Literal, Optional, Sequence
from .base_scanner import Scanner, ScannerResult

class BanCompetitors(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    competitors: Optional[Sequence[str]] = None
    redact: Optional[bool] = None
    result: Optional[ScannerResult] = None