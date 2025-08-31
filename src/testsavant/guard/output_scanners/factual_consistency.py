from pydantic import confloat
from typing import Literal, Optional, Sequence
from ..input_scanners.base_scanner import Scanner, ScannerResult

class FactualConsistency(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    minimum_score: Optional[float] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    _requires_input_prompt: bool = True