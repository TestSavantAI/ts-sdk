# Migration from InputGuard and OutputGuard to Guardrail

The public SDK now has a single `Guardrail` client for pre-inference text evaluation.

| Old | New |
| --- | --- |
| `InputGuard(API_KEY=..., fail_fast=...)` | `Guardrail(API_KEY=..., fail_fast=...)` |
| `OutputGuard(...)` | `Guardrail(...)` (pass the actual text under examination to `scan`) |
| `add_scanner(scanner)` | `add_guardrail(guard)` or `add_guard(guard)`; legacy alias still works |
| `remove_all_scanners()` | `clear_guardrails()` |
| `get_available_scanners()` | `get_available_guardrails()` |
| `guard.scan(prompt, is_async=True)` | Same coroutine behavior; prefer `await guard.ascan(prompt)` |
| `ScannerResult.is_valid` | `GuardrailResult.is_valid`, also `.valid`, `.decision`, `.results` |

### Example

```python
from testsavant.guard import Guardrail
from testsavant.guard.guardrails import PromptInjection, NSFW, ContextualAttack

guard = Guardrail(API_KEY='...', remote_addr='https://your-server.example',
                  endpoint='/guard/prompt-input', fail_fast=False)
guard.add_guard(PromptInjection(tag='base', threshold=0.8))
guard.add_guard(NSFW(tag='base', threshold=0.9))
guard.add_guard(ContextualAttack(tag='base', accepted_topic=['Finance'],
                               target_agent_role='Financial information assistant'))
result = guard.scan('I need help interpreting my bank statement')
```

### Important compatibility boundaries

The client now always submits a **single text field named `prompt`**. Former output guardrails are no longer sent an independent `output` field; if you are inspecting a model response, pass that response as the text being checked. Some semantic checks (factual consistency, instruction adherence, role alignment) require reference context in guardrail parameters, and cannot be applied without it. The server must support the selected guardrail name and model tag.

The old SDK's `input_scanners`/`output_scanners` Python descriptor classes are retained for migration, but the public API no longer differentiates input and output guard clients. The legacy aliases `InputGuard`/`OutputGuard` exist only in the underlying `guard.py` module and are **not** exported as the recommended top-level API. `OutputGuard` is an alias, *not* an implementation of the old two-text output endpoint.

The endpoint name is **not inferred**. Default `/guard/prompt-input` was preserved from the original SDK; configure it if your upgraded FastAPI service uses a different URL. Legacy image features use separate routes.

### Tuning

```python
from testsavant.guard import BinaryGuardrailTuner
from testsavant.guard.guardrails import PromptInjection

tuner = BinaryGuardrailTuner.from_guardrail_class(
    guardrail_cls=PromptInjection,
    search_space={'threshold': [(0.7, 1), (0.8, 1), (0.9, 1)]},
    fixed_guardrail_kwargs={'tag': 'base'},
)
```

Legacy `from_input_scanner_class` remains usable, including a default threshold search grid for legacy scanners without an explicit search space.
