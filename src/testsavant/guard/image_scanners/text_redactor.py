from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult
from ..input_scanners import PromptInjection, Language, NSFW, Toxicity, Anonymize

class ImageTextRedactor(Scanner):
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    nested_scanners: Optional[Dict[str, Dict]] = None
    redact_text_type: Optional[Literal["all", "anonymizer"]] = "anonymizer"
    shade_color: Optional[str] = None

    def add_text_scanner(self, scanner: Scanner):
        # scanners should one of prompt injection, language, nsfw, toxicity or anonymizer
        assert isinstance(scanner, Scanner), "scanner must be an instance of Scanner"
        assert scanner.__class__.__name__ in [
            "PromptInjection",
            "Language",
            "NSFW",
            "Toxicity",
            "Anonymize"
        ], f"scanner must be one of {['PromptInjection', 'Language', 'NSFW', 'Toxicity', 'Anonymize']}"
        if not self.nested_scanners:
            self.nested_scanners={}
        self.nested_scanners[scanner.name] = scanner.model_dump()
