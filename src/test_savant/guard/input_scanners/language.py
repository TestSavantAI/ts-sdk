from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class Language(Scanner):
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    tag: Literal["base"]
    valid_languages: Optional[list[Literal[
        "ja", "nl", "ar", "pl", "de", "it", "pt", "tr", "es", "hi",
        "el", "ur", "bg", "en", "fr", "zh", "ru", "th", "sw", "vi"
    ]]] = None
    result: Optional[ScannerResult] = None