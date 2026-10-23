# Changelog

## 0.1.0 — Unified guardrail client

- Replaced separate InputGuard/OutputGuard client workflows with `testsavant.guard.Guardrail`.
- Payload matches the existing `AnalyzePromptRequest` shape (`prompt`, `config`, `use`, `metadata`).
- Added 25 named Pydantic guardrail request descriptors, including ContextualAttack.
- Added add/remove/replace/clear guardrail registration, `add_scanner` migration alias, and support for raw dict descriptors.
- Kept async/sync transport, callback handling, API errors, discovery, project ID, metadata and cache configuration.
- Normalized modern `valid`/`decision`/`results` responses and historic `is_valid`/`scanners`/`validity` responses, with strict fail-closed schema errors.
- Preserved BinaryGuardrailTuner, optimizer utilities, and legacy scanner class support; added `from_guardrail_class` tuner construction.
- Preserved explicit legacy image upload/download helpers, separate from the unified text-only API.
- Added 21-cell executable example notebook and 33 automated unit/regression tests.
- Archived old input/output notebooks, stripped stored outputs, and excluded the original `.env` file from distribution.

**Compatibility note:** the default API path remains `/guard/prompt-input`; configure `endpoint=` if the upgraded backend uses another route. The SDK is a client, not the server-side inference engine.
