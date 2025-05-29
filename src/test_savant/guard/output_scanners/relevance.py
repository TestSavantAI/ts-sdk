from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class Relevance(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["small", "base", "large"]
    result: Optional[ScannerResult] = None
