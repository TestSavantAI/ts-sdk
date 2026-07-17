from pydantic import BaseModel, Field
from typing import ClassVar, Dict, Optional, List, Any
import json

class ScannerResult(BaseModel):
    sanitized_prompt: Optional[str] = None
    is_valid: bool
    scanners: Dict[str, float]
    validity: Dict[str, bool]
    files: Optional[Dict[str, List[str]]] = None
    nested_scanners: Optional[Dict[str, Any]] = None
    sanitized_output: Optional[str] = None

class Scanner(BaseModel):
    # tag: str
    optimization_search_space: ClassVar[Optional[Dict[str, List[Any]]]] = None
    optimization_init_kwargs: ClassVar[Dict[str, Any]] = {}
    optimization_defaults: ClassVar[Dict[str, Any]] = {}

    tag: str = Field(
        ..., 
        description="Scanner model tag. For available models, see: https://docs.testsavant.ai"
    )
    result: Optional[ScannerResult] = None

    def _serialize_request(self) -> Dict:
        class_name = self.__class__.__name__
        name = f"{class_name}:{self.tag}"
        params = self.model_dump(exclude={"tag"})
        params = {k: v for k, v in params.items() if not k.startswith("_") and v is not None and k != "result"}
        return {'name': name, 'params': params, 'type': class_name}
    
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


    @property
    def name(self) -> str:
        return f"{self.__class__.__name__}:{self.tag}"

    @classmethod
    def get_optimization_search_space(cls) -> Dict[str, List[Any]]:
        if cls.optimization_search_space is None:
            raise ValueError(f"{cls.__name__} does not define an optimization search space.")
        return dict(cls.optimization_search_space)

    @classmethod
    def get_optimization_defaults(cls) -> Dict[str, Any]:
        return dict(cls.optimization_defaults)

    @classmethod
    def build_optimized_instance(
        cls,
        config: Dict[str, Any],
        fixed_kwargs: Optional[Dict[str, Any]] = None,
    ) -> "Scanner":
        params = dict(cls.optimization_init_kwargs)
        if fixed_kwargs is not None:
            params.update(fixed_kwargs)
        params.update(config)
        return cls(**params)