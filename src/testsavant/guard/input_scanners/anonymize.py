from pydantic import confloat
from typing import Literal, Optional, Dict, List, Annotated
from .base_scanner import Scanner, ScannerResult
import json

class Anonymize(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    use_faker: Optional[bool] = False
    preamble: Optional[str] = None
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
    redact: bool = False
    entity_types:  List[Annotated[str, Literal[
            "CREDIT_CARD",
            "CRYPTO",
            "EMAIL_ADDRESS",
            "IBAN_CODE",
            "IP_ADDRESS",
            "PERSON",
            "PHONE_NUMBER",
            "US_SSN",
            "US_BANK_NUMBER",
            "CREDIT_CARD_RE",
            "UUID",
            "EMAIL_ADDRESS_RE",
            "US_SSN_RE",
            "USERNAME",
            "PASSWORD",
        ]]] = [
            "CREDIT_CARD",
            "CRYPTO",
            "EMAIL_ADDRESS",
            "IBAN_CODE",
            "IP_ADDRESS",
            "PERSON",
            "PHONE_NUMBER",
            "US_SSN",
            "US_BANK_NUMBER",
            "CREDIT_CARD_RE",
            "UUID",
            "EMAIL_ADDRESS_RE",
            "US_SSN_RE",
            "USERNAME",
            "PASSWORD",
        ]
    allowed_names: Optional[List[str]] = None


