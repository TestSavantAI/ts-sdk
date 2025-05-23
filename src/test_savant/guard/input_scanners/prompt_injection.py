from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class PromptInjection(Scanner):
    threshold: confloat(ge=0.0, le=1.0) = 0.5
    tag: Literal["tiny", "small", "base", "large"]
    result: Optional[ScannerResult] = None
