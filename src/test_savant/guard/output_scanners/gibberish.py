from pydantic import confloat
from typing import Literal, Optional
from ..input_scanners.base_scanner import Scanner, ScannerResult

class Gibberish(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base", "small-unified"]
    result: Optional[ScannerResult] = None