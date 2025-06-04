from pydantic import confloat
from typing import Literal, Optional, Sequence
from .base_scanner import Scanner, ScannerResult

class FactualConsistency(Scanner):
    minimum_score: Optional[float] = None
    tag: Literal["small", "base", "large"]
    result: Optional[ScannerResult] = None
    _requires_input_prompt: bool = True