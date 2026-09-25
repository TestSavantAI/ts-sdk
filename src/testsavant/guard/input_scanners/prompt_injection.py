from pydantic import confloat
from typing import ClassVar, Dict, Literal, Optional
from .base_scanner import Scanner, ScannerResult
import json

class PromptInjection(Scanner):
    """
        For all available tags, check: https://docs.testsavant.ai/docs/v1/python/input-scanners
    """
    optimization_search_space: ClassVar[Dict[str, list]] = {
        "threshold": [(round(i * 0.025, 3), 1.0) for i in range(41)],
        "chunk_size": [
            (50, 0.1),
            (75, 0.2),
            (100, 0.3),
            (125, 0.4),
            (150, 0.5),
            (175, 0.6),
            (200, 0.7),
            (225, 0.8),
            (250, 0.9),
            (275, 1.0),
            (300, 1.0),
            (325, 1.0),
            (350, 1.0),
        ],
        "overlap": [
            (10, 1.0),
            (20, 0.8),
            (30, 0.5),
            (40, 0.3),
            (50, 0.1),
        ],
    }
    optimization_init_kwargs: ClassVar[Dict[str, str]] = {"tag": "base"}
    optimization_defaults: ClassVar[Dict[str, float]] = {
        "epochs": 8,
        "batch_size": 32,
        "top_k": 10,
    }

    threshold: Optional[confloat(ge=0.0, le=1.0)] = None
    chunk_size: int = 300
    overlap: int = 50
    tag: Literal["base"]
    result: Optional[ScannerResult] = None
