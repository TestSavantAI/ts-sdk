from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class LLMJudge(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    tag: str = "default"
    result: Optional[ScannerResult] = None
    num_retry: Optional[int] = None
