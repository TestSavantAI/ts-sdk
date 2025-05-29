from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class Anonymize(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    use_faker: Optional[bool] = None
    preamble: Optional[str] = None
    tag: Literal["base", "large"]
    result: Optional[ScannerResult] = None