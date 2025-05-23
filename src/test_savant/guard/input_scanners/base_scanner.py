from pydantic import BaseModel
from typing import Dict, List, Optional
import json

class ScannerResult(BaseModel):
    label: Optional[str] = None
    score: Optional[float] = None
    

class Scanner(BaseModel):
    tag: str
    result: Optional[ScannerResult] = None

    def _serialize_request(self) -> Dict:
        class_name = self.__class__.__name__
        name = f"{class_name}:{self.tag}"
        params = self.model_dump(exclude={"tag"})
        params = {k: v for k, v in params.items() if not k.startswith("_") and v is not None and k != "result"}
        return {'name': name, 'params': params}
    
    def _serialize_all(self) -> Dict:
        class_name = self.__class__.__name__
        name = f"{class_name}:{self.tag}"
        params = self.model_dump(exclude={"tag"})
        params = {k: v for k, v in params.items() if not k.startswith("_") and v is not None and k != "result"}
        return {'name': name, 'params': params, 'result': self.result.model_dump() if self.result else None}
    
    def json(self, request_only=False) -> str:
        serialized = self._serialize_request() if request_only else self._serialize_all()
        return json.dumps(serialized, indent=2)
    
    def to_dict(self, request_only=False) -> str:
        return self._serialize_request() if request_only else self._serialize_all()
    
    def is_valid(self) -> bool:
        raise NotImplementedError("Subclasses should implement this method.")

