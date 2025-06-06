from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult

class ImageTextRedactor(Scanner):
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    nested_scanners: Optional[Dict[str, Dict]] = None
    redact_text_type: Optional[Literal["all", "anonymizer"]] = "anonymizer"
    shade_color: Optional[str] = None

    def add_text_scanner(self, scanner: Scanner):
        assert isinstance(scanner, Scanner), "scanner must be an instance of Scanner"
        if not self.nested_scanners:
            self.nested_scanners={}
        self.nested_scanners[scanner.name] = scanner.model_dump()
