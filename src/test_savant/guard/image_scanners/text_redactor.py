from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult

class ImageTextRedactor(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    nested_scanners: Optional[Dict[str, Dict]] = None
    redact_text_type: Optional[Literal["all", "anonymizer"]] = "anonymizer"
    shade_color: Optional[str] = None

    def add_text_scanner(self, scanner: Scanner):
        assert type(scanner) != Scanner, f"Provide a Scanner, the current scanner is {type(scanner)}"
        if not self.nested_scanners:
            self.nested_scanners={}
        self.nested_scanners[scanner.name] = scanner.model_dump()
