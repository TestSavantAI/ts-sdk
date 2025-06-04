from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import ImageScanner, ScannerResult
from ..input_scanners.base_scanner import Scanner

class ImageTextRedactor(ImageScanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    nested_scanners: Optional[Dict[str, Dict]] = None

    def add_text_scanner(self, scanner: Scanner):
        if not self.nested_scanners:
            self.nested_scanners={}
        self.nested_scanners[scanner.name] = scanner.model_dump()
