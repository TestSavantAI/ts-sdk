from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult
import json

class PromptInjection(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["tiny", "small", "base", "large"]
    result: Optional[ScannerResult] = None
