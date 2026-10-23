"""TestSavantAI unified Guardrail SDK.

Primary usage: ``Guardrail`` + named descriptors from ``testsavant.guard.guardrails``.
Legacy InputGuard/OutputGuard imports remain internal migration aliases but are
no longer separate APIs.
"""
from .guard import Guardrail, GuardrailResult, ResponseFormatError
from .models import AnalyzePromptRequest, RequestConfig, RequestScannerConfig, GuardrailDecision
from .guardrails import GuardSpec, CustomGuard, GUARDRAIL_TYPES, make_guardrail
from ._exceptions import (
    APIStatusError, BadRequestError, AuthenticationError, PermissionDeniedError,
    NotFoundError, ConflictError, UnprocessableEntityError, RateLimitError,
    InternalServerError, TsGuardError,
)
from .optimization import RunningStat, OptunaOptimizer, build_discrete_configs, create_optimizer
from .tuning import (
    BinaryClassificationMetrics, BinaryGuardrailTuner, GuardrailCandidateResult,
    GuardrailFitResult, compute_binary_classification_metrics, harmonic_mean,
)

__all__ = [
    "Guardrail", "GuardrailResult", "GuardrailDecision", "ResponseFormatError",
    "AnalyzePromptRequest", "RequestConfig", "RequestScannerConfig",
    "GuardSpec", "CustomGuard", "GUARDRAIL_TYPES", "make_guardrail",
    "APIStatusError", "BadRequestError", "AuthenticationError", "PermissionDeniedError",
    "NotFoundError", "ConflictError", "UnprocessableEntityError", "RateLimitError",
    "InternalServerError", "TsGuardError", "RunningStat", "OptunaOptimizer",
    "build_discrete_configs", "create_optimizer", "BinaryClassificationMetrics",
    "BinaryGuardrailTuner", "GuardrailCandidateResult", "GuardrailFitResult",
    "compute_binary_classification_metrics", "harmonic_mean",
]
