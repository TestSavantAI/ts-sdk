from pydantic import confloat
from typing import Literal, Optional, Dict
from .base_scanner import Scanner, ScannerResult
import json

class PromptInjectionResult(ScannerResult):
    label: Optional[str] = None
    score: Optional[float] = None
    prompt_injection: Optional[bool] = None
    prompt_injection_score: Optional[float] = None
    
    # json
    def json(self) -> str:
        return json.dumps(self.model_dump(), indent=2)

    def _serialize(self) -> Dict:
        return self.model_dump(exclude_none=True)


class PromptInjection(Scanner):
    threshold: confloat(ge=0.0, le=1.0) = 0.5
    tag: Literal["tiny", "small", "base", "large"]
    result: Optional[PromptInjectionResult] = None
