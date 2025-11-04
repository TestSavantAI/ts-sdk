from typing import Literal, Optional
from .base_scanner import Scanner, ScannerResult

class LLM(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: Literal["default"] = "default"
    instruction: str
    result: Optional[ScannerResult] = None
    num_retry: Optional[int] = None
