from pydantic import confloat
from typing import Literal, Optional, List
from .base_scanner import Scanner, ScannerResult
from ..common.common import AnonymizeEntity


class Anonymize(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    use_faker: Optional[bool] = False
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    redact: bool = False
    entities: Optional[List[AnonymizeEntity]] = None


