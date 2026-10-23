"""Wire schemas and normalized results for the unified AnalyzePrompt API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RequestConfig(BaseModel):
    """Shared request execution options. Extra fields pass through to the server."""
    model_config = ConfigDict(extra="allow")
    fail_fast: bool = False


class RequestScannerConfig(BaseModel):
    """The server's ``use`` item shape (a guardrail name plus parameters)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not isinstance(value, str) or value.count(":") != 1:
            raise ValueError("name must be '<GuardrailName>:<model_tag>'")
        base, tag = value.split(":", 1)
        if not base or not tag or any(c.isspace() for c in tag):
            raise ValueError("name must be '<GuardrailName>:<model_tag>'")
        return value


class AnalyzePromptRequest(BaseModel):
    """Matches the FastAPI server's AnalyzePromptRequest public contract."""
    model_config = ConfigDict(extra="forbid")
    prompt: str
    config: Optional[RequestConfig] = Field(default_factory=RequestConfig)
    use: List[RequestScannerConfig]
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must contain non-whitespace text")
        return value

    @field_validator("use")
    @classmethod
    def validate_use(cls, value: List[RequestScannerConfig]) -> List[RequestScannerConfig]:
        if not value:
            raise ValueError("At least one guardrail must be specified in 'use'")
        names = [item.name for item in value]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate guardrail names are ambiguous; use each name/tag once")
        return value


class GuardrailDecision(BaseModel):
    """Normalized outcome of one remote guardrail.

    A skipped/failed operation has ``valid=None`` and ``decision=None``;
    those must not be treated as successful validations.
    """
    model_config = ConfigDict(extra="allow")
    name: str
    status: str = "completed"
    valid: Optional[bool] = None
    decision: Optional[Literal["valid", "invalid"]] = None
    reason_codes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistency(self) -> "GuardrailDecision":
        if self.valid is None and self.decision is not None:
            self.valid = self.decision == "valid"
        if self.decision is None and self.valid is not None:
            self.decision = "valid" if self.valid else "invalid"
        if self.decision is not None and self.valid != (self.decision == "valid"):
            raise ValueError("Guardrail result has contradictory valid and decision values")
        if self.status == "completed" and self.valid is None:
            raise ValueError("Completed guardrail lacks a validity decision")
        if self.status in {"error", "failed", "skipped"} and self.valid is True:
            raise ValueError("Unexecuted/failed guardrail cannot be valid")
        return self


class GuardrailResult(BaseModel):
    """Normalized API result, including old scanner fields when returned.

    Access `raw_response` for fields the server returns but the client doesn't
    normalize. Raw responses are excluded from `model_dump` to avoid duplicates.
    """
    model_config = ConfigDict(extra="allow")
    is_valid: bool
    valid: bool
    decision: Literal["valid", "invalid"]
    results: List[GuardrailDecision] = Field(default_factory=list)
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    sanitized_prompt: Optional[str] = None
    sanitized_output: Optional[str] = None
    scanners: Dict[str, float] = Field(default_factory=dict)
    validity: Dict[str, bool] = Field(default_factory=dict)
    files: Optional[Dict[str, List[str]]] = None
    nested_scanners: Optional[Dict[str, Any]] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict, exclude=True, repr=False)

    @classmethod
    def from_api_response(cls, body: Any, request_id: Optional[str] = None) -> "GuardrailResult":
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object for the guardrail response")

        from_explicit = [body.get(key) for key in ("valid", "is_valid") if isinstance(body.get(key), bool)]
        decision = body.get("decision")
        if decision is not None:
            if decision not in ("valid", "invalid"):
                raise ValueError("Unrecognized overall decision")
            from_explicit.append(decision == "valid")
        if not from_explicit:
            # Old APIs sometimes returned only scanner validity maps.
            validity_map = body.get("validity")
            if isinstance(validity_map, dict) and validity_map and all(isinstance(x, bool) for x in validity_map.values()):
                from_explicit = [all(validity_map.values())]
        if not from_explicit or len(set(from_explicit)) > 1:
            raise ValueError("Missing or contradictory overall validity in server response")
        overall = from_explicit[0]

        items: List[GuardrailDecision] = []
        raw_items = body.get("results", [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise ValueError("'results' must be a list of guardrail outcomes")
        for item in raw_items:
            items.append(GuardrailDecision.model_validate(item))
        if not items and isinstance(body.get("validity"), dict):
            items = [GuardrailDecision(name=k, valid=v) for k, v in body["validity"].items()]
        if overall and any(item.valid is not True for item in items):
            raise ValueError("Server reported valid but a guardrail was invalid or incomplete")
        if not overall and items and all(item.valid is True for item in items):
            # This can occur when a separate execution error triggered fail-closed;
            # the server's global verdict remains authoritative.
            pass
        reserved = {"valid", "is_valid", "decision", "results", "raw_response"}
        known = {"metadata", "execution", "sanitized_prompt", "sanitized_output",
                 "scanners", "validity", "files", "nested_scanners"}
        return cls(
            is_valid=overall, valid=overall, decision="valid" if overall else "invalid",
            results=items,
            request_id=body.get("request_id") or request_id,
            raw_response=dict(body),
            **{k: v for k, v in body.items() if k not in reserved and k in known},
        )


__all__ = ["RequestConfig", "RequestScannerConfig", "AnalyzePromptRequest", "GuardrailDecision", "GuardrailResult"]
