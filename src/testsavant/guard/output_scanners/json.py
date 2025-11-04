from pydantic import confloat
from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class JSON(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    tag: Literal["default"] = "default"
    repair: Optional[bool] = False
    result: Optional[ScannerResult] = None
    num_elements: int