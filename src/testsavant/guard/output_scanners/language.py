from pydantic import confloat
from typing import Literal, Optional, Dict
from ..input_scanners.base_scanner import Scanner, ScannerResult
import json

class Language(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/output-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    valid_languages: Optional[list[Literal[
        "ja", "nl", "ar", "pl", "de", "it", "pt", "tr", "es", "hi",
        "el", "ur", "bg", "en", "fr", "zh", "ru", "th", "sw", "vi"
    ]]] = None
    result: Optional[ScannerResult] = None