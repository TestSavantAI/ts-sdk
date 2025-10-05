from pydantic import BaseModel
from typing import Literal, Optional, List

class EntityMatch(BaseModel):
    values: Optional[List[str]] = None
    mode: Literal["whitelist", "blacklist"]
    entity_type: str
