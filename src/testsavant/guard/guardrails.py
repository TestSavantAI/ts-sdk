"""Named, typed configuration objects for TestSavantAI's unified guardrail API.

These are *client-side request descriptors*. The decision questions and execution
happen in the remote server; instantiating these classes does not run a model.
"""
from __future__ import annotations

import json
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GuardSpec(BaseModel):
    """Base for named guardrail configurations with model routing by ``tag``.

    Additional parameters pass through to the server for forward compatibility.
    The server is the authoritative validator for guardrail-specific settings.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)
    guard_name: ClassVar[Optional[str]] = None
    tag: str = "base"
    threshold: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("tag")
    @classmethod
    def check_tag(cls, value: str) -> str:
        if not value or value.strip() != value or ":" in value:
            raise ValueError("tag must be a nonempty model-routing identifier without ':'")
        return value

    @property
    def name(self) -> str:
        return f"{self.guard_name or self.__class__.__name__}:{self.tag}"

    def to_dict(self, request_only: bool = True) -> Dict[str, Any]:
        params = self.model_dump(exclude={"tag"}, exclude_none=True, mode="json")
        return {"name": self.name, "params": params}

    def json(self, request_only: bool = True) -> str:
        """Compatibility with legacy scanner JSON serialization."""
        return json.dumps(self.to_dict(request_only=request_only), indent=2)

    def with_params(self, **changes: Any) -> "GuardSpec":
        """Produce an updated configuration without changing an existing instance."""
        return type(self).model_validate({**self.model_dump(), **changes})


class PromptInjection(GuardSpec):
    """Detects direct and indirect prompt injection and adversarial instruction override."""
    pass


class ContextualAttack(GuardSpec):
    """Injection detection plus optional allowed intent/topic and agent-role scope."""
    accepted_intent: Optional[Union[str, List[str]]] = None
    accepted_topic: Optional[Union[str, List[str]]] = None
    target_agent_role: Optional[Union[str, Dict[str, Any]]] = None
    input_mode: Optional[Literal["instruction", "content", "mixed", "auto"]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_topic_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "accepted_top" in data:
            if "accepted_topic" in data:
                raise ValueError("Use accepted_topic, not both accepted_topic and accepted_top")
            data = dict(data)
            data["accepted_topic"] = data.pop("accepted_top")
        return data


class HarmfulRequest(GuardSpec):
    pass


class Toxicity(GuardSpec):
    pass


class NSFW(GuardSpec):
    pass


class Gibberish(GuardSpec):
    pass


class FactualConsistency(GuardSpec):
    reference: Optional[Union[str, List[str]]] = None


class Bias(GuardSpec):
    pass


class Opinionated(GuardSpec):
    pass


class Intent(GuardSpec):
    accepted_intent: Optional[Union[str, List[str]]] = None


class Topic(GuardSpec):
    accepted_topic: Optional[Union[str, List[str]]] = None


class PII(GuardSpec):
    pass


class SystemPromptLeakage(GuardSpec):
    pass


class ToolCall(GuardSpec):
    allowed_tools: Optional[List[str]] = None
    target_agent_role: Optional[str] = None
    tool_trace: Optional[Dict[str, Any]] = None


class CodeDetection(GuardSpec):
    pass


class ProgrammingLanguage(GuardSpec):
    accepted_languages: Optional[List[str]] = None


class NaturalLanguage(GuardSpec):
    accepted_languages: Optional[List[str]] = None


class Sentiment(GuardSpec):
    blocked_sentiments: Optional[List[str]] = None


class Refusal(GuardSpec):
    pass


class MaliciousURL(GuardSpec):
    pass


class LanguageSimilarity(GuardSpec):
    reference_language: Optional[str] = None


class PhishingSocialEngineering(GuardSpec):
    pass


class MalwareCyberAbuse(GuardSpec):
    pass


class Misinformation(GuardSpec):
    reference: Optional[Union[str, List[str]]] = None


class AgentRoleAlignment(GuardSpec):
    target_agent_role: Optional[Union[str, Dict[str, Any]]] = None


GUARDRAIL_TYPES = {
    cls.__name__: cls for cls in (
        PromptInjection, ContextualAttack, HarmfulRequest, Toxicity, NSFW,
        Gibberish, FactualConsistency, Bias, Opinionated, Intent, Topic, PII,
        SystemPromptLeakage, ToolCall, CodeDetection, ProgrammingLanguage,
        NaturalLanguage, Sentiment, Refusal, MaliciousURL, LanguageSimilarity,
        PhishingSocialEngineering, MalwareCyberAbuse, Misinformation,
        AgentRoleAlignment,
    )
}


def make_guardrail(name: str, tag: str = "base", **params: Any) -> GuardSpec:
    """Build a named guardrail, including custom server-registered guardrails.

    A provided ``name`` can include a tag (e.g. ``'NSFW:large'``). The default
    tag is only used when the name has no suffix. Custom names are supported.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Guardrail name must be a nonempty string")
    if ":" in name:
        base, parsed_tag = name.rsplit(":", 1)
        if not base or not parsed_tag:
            raise ValueError("Use '<guardrail>:<tag>'")
        if tag != "base" and tag != parsed_tag:
            raise ValueError("Conflicting model tags")
        tag = parsed_tag
        name = base
    cls = GUARDRAIL_TYPES.get(name)
    if cls is not None:
        return cls(tag=tag, **params)
    return CustomGuard(registered_name=name, tag=tag, **params)


class CustomGuard(GuardSpec):
    """Client-side configuration for server-defined or future guardrails."""
    registered_name: str = Field(exclude=True)

    @property
    def name(self) -> str:
        if not self.registered_name or ":" in self.registered_name:
            raise ValueError("registered_name must be a bare nonempty guardrail name")
        return f"{self.registered_name}:{self.tag}"


__all__ = ["GuardSpec", "CustomGuard", "GUARDRAIL_TYPES", "make_guardrail", *GUARDRAIL_TYPES]
