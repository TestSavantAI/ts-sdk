from pydantic import BaseModel
from typing import Literal, Optional, List

class AnonymizeEntity(BaseModel):
    """Entity to be anonymized. For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners"""
    entity_type: str
    mode: Literal["whitelist", "blacklist"]
    values: Optional[List[str]] = None
