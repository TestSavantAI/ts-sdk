from pydantic import confloat
from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class LanguageSame(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    _requires_input_prompt: bool = True