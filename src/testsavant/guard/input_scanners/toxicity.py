from pydantic import confloat
from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class Toxicity(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    # min_toxicity_level: Optional[Literal["low", "mild", "extreme"]] = None
    result: Optional[ScannerResult] = None