from pydantic import confloat
from typing import Literal, Optional, Sequence
from ..input_scanners.base_scanner import Scanner, ScannerResult

class Code(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    threshold: confloat(ge=0.0, le=1.0) = 0.6
    tag: Literal["base"]
    languages: list[str]
    is_blocked: bool = True
    result: Optional[ScannerResult] = None
