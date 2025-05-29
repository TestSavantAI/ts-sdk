from ..input_scanners import ScannerResult as ScannerResultInput, Scanner as ScannerInput
from typing import Optional

class ScannerResult(ScannerResultInput):
    sanitized_output: Optional[str] = None
  
class Scanner(ScannerInput):
    result: Optional[ScannerResult] = None  