from pydantic import confloat
from typing import Literal, Optional, Sequence
from ..input_scanners.base_scanner import Scanner, ScannerResult

class BanCompetitors(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    competitors: Optional[Sequence[str]] = None
    redact: Optional[bool] = None
    result: Optional[ScannerResult] = None