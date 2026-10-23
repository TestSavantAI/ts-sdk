"""One HTTP client for TestSavantAI's unified guardrail endpoint.

This module intentionally doesn't run Jev or implement guardrail policies: the
remote API owns guardrail execution. The SDK collects named configurations and
sends one AnalyzePromptRequest JSON payload, with sync/async support.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Union
import httpx
from pydantic import BaseModel

from ._exceptions import (
    TsGuardError, APIStatusError, BadRequestError, AuthenticationError,
    PermissionDeniedError, NotFoundError, ConflictError, UnprocessableEntityError,
    RateLimitError, InternalServerError,
)
from .guardrails import GuardSpec, make_guardrail
from .models import (
    AnalyzePromptRequest, RequestConfig, RequestScannerConfig,
    GuardrailResult,
)
from .input_scanners.base_scanner import Scanner

Callback = Callable[[GuardrailResult], Union[None, Awaitable[None]]]
REMOTE_TS_API_ADDRESS = "https://api.testsavant.ai"
DEFAULT_ANALYZE_ENDPOINT = "/guard/prompt-input"  # existing SDK route; override for new deployments


class ResponseFormatError(TsGuardError):
    """The remote service returned malformed, incomplete or inconsistent JSON."""


class Guardrail:
    """Client for evaluating a prompt using one or many configured guardrails.

    One scan produces one HTTP POST with a ``prompt``, ``config``, ``use``, and
    optional ``metadata``. Batching the Jev questions by model tag is performed
    by the *server*; this client does not send one HTTP request per guardrail.

    Parameters follow the original SDK naming for easy migration. The API path
    is configurable because deployments may use a new endpoint name.
    """

    def __init__(
        self,
        API_KEY: Optional[str] = None,
        PROJECT_ID: Optional[str] = None,
        remote_addr: Optional[str] = None,
        fail_fast: bool = True,
        *,
        endpoint: Optional[str] = None,
        timeout: float = 30.0,
        cache: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        sync_client: Optional[httpx.Client] = None,
        async_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.API_KEY = API_KEY or os.getenv("TEST_SAVANT_API_KEY")
        if not self.API_KEY:
            raise ValueError("Provide API_KEY or set TEST_SAVANT_API_KEY")
        self.PROJECT_ID = PROJECT_ID if PROJECT_ID is not None else os.getenv("TEST_SAVANT_PROJECT_ID")
        self.remote_addr = (remote_addr or os.getenv("TEST_SAVANT_REMOTE_ADDR") or REMOTE_TS_API_ADDRESS).rstrip("/")
        self.endpoint = endpoint or os.getenv("TEST_SAVANT_GUARDRAIL_ENDPOINT") or DEFAULT_ANALYZE_ENDPOINT
        if not self.endpoint.startswith("/") or self.endpoint.startswith("//"):
            raise ValueError("endpoint must be a relative API path beginning with a single '/' ")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout
        self.fail_fast = bool(fail_fast)
        self.cache = dict(cache) if cache is not None else None
        self.default_metadata = dict(metadata or {})
        self.guardrails: List[Any] = []
        self._sync_client = sync_client
        self._async_client = async_client
        self._owns_sync = sync_client is None
        self._owns_async = async_client is None
        self._closed = False

    @property
    def scanners(self) -> List[Any]:
        """Deprecated alias retained for SDK extensions and existing tuning code."""
        return self.guardrails

    @scanners.setter
    def scanners(self, value: Optional[List[Any]]) -> None:
        self.guardrails = list(value or [])

    def _to_use(self, guard: Any) -> RequestScannerConfig:
        if isinstance(guard, RequestScannerConfig):
            return guard.model_copy(deep=True)
        if isinstance(guard, str):
            return RequestScannerConfig.model_validate(make_guardrail(guard).to_dict())
        if isinstance(guard, (GuardSpec, Scanner)):
            data = guard.to_dict(request_only=True)
        elif isinstance(guard, BaseModel):
            data = guard.model_dump(mode="json", exclude_none=True)
        elif isinstance(guard, Mapping):
            data = dict(guard)
        else:
            raise TypeError("Guard must be GuardSpec, Scanner, name string, or {'name', 'params'} dict")
        # Older Scanner descriptors include an extra 'type' field; the new server
        # requires only name and params. Do not send the legacy field.
        data = {key: data[key] for key in ("name", "params") if key in data}
        return RequestScannerConfig.model_validate(data)

    def add_guardrail(self, guard: Any) -> "Guardrail":
        item = self._to_use(guard)
        if item.name in {self._to_use(existing).name for existing in self.guardrails}:
            raise ValueError(f"Duplicate guardrail {item.name!r}; use replace_guardrail()")
        self.guardrails.append(guard)
        return self

    def add_guard(self, guard: Any) -> "Guardrail":
        """Convenience alias for add_guardrail()."""
        return self.add_guardrail(guard)

    def add_scanner(self, scanner: Any) -> "Guardrail":
        """Backwards compatible alias for older scanner configuration objects."""
        return self.add_guardrail(scanner)

    def replace_guardrail(self, guard: Any) -> "Guardrail":
        new = self._to_use(guard)
        self.guardrails = [item for item in self.guardrails if self._to_use(item).name != new.name]
        self.guardrails.append(guard)
        return self

    def remove_guardrail(self, guard: Union[str, Any]) -> bool:
        name = guard if isinstance(guard, str) else self._to_use(guard).name
        before = len(self.guardrails)
        self.guardrails = [item for item in self.guardrails if self._to_use(item).name != name]
        return len(self.guardrails) < before

    def clear_guardrails(self) -> None:
        self.guardrails.clear()

    def remove_all_scanners(self) -> None:
        """Backwards compatible alias for clear_guardrails()."""
        self.clear_guardrails()

    def _scanners_to_dict(self, scanners: Optional[Sequence[Any]] = None, request_only: bool = True,
                          multimodal: bool = False):
        """Compatibility utility for extensions from the old SDK.

        The unified text endpoint has no multimodal upload parameter.
        """
        items = list(self.guardrails if scanners is None else scanners)
        if not items:
            raise ValueError("No guardrails have been added")
        return [self._to_use(item).model_dump(mode="json") for item in items], set()

    def build_request(
        self,
        prompt: str,
        *,
        guards: Optional[Sequence[Any]] = None,
        config: Optional[Union[RequestConfig, Mapping[str, Any]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> AnalyzePromptRequest:
        """Preview and validate the exact body that will be posted to FastAPI."""
        configured = list(self.guardrails if guards is None else guards)
        guard_items = [self._to_use(item) for item in configured]
        cfg: Dict[str, Any] = {"fail_fast": self.fail_fast}
        if self.PROJECT_ID is not None:
            cfg["project_id"] = self.PROJECT_ID
        if self.cache is not None:
            cfg["cache"] = dict(self.cache)
        if config is not None:
            if isinstance(config, BaseModel):
                cfg.update(config.model_dump(exclude_unset=True, exclude_none=True, mode="json"))
            elif isinstance(config, Mapping):
                cfg.update(dict(config))
            else:
                raise TypeError("config must be a mapping or Pydantic RequestConfig")
        meta = dict(self.default_metadata)
        if metadata is not None:
            if not isinstance(metadata, Mapping):
                raise TypeError("metadata must be a mapping")
            meta.update(metadata)
        return AnalyzePromptRequest(prompt=prompt, config=RequestConfig.model_validate(cfg),
                                    use=guard_items, metadata=meta or None)

    def _body(self, request: Union[AnalyzePromptRequest, Mapping[str, Any], BaseModel]) -> Dict[str, Any]:
        if isinstance(request, BaseModel):
            data = request.model_dump(mode="json")
        elif isinstance(request, Mapping):
            data = dict(request)
        else:
            raise TypeError("Request must be AnalyzePromptRequest, Pydantic model, or a dict")
        return AnalyzePromptRequest.model_validate(data).model_dump(mode="json", exclude_none=True)

    def _url(self, endpoint: Optional[str] = None) -> str:
        return self.remote_addr + (endpoint or self.endpoint)

    def _headers(self) -> Dict[str, str]:
        return {"x-api-key": self.API_KEY, "Accept": "application/json", "Content-Type": "application/json"}

    @staticmethod
    def _read_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except (ValueError, UnicodeDecodeError):
            raise ResponseFormatError(f"Expected JSON response, got HTTP {response.status_code} non-JSON data")

    @staticmethod
    def _raise_on_error(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError):
            body = None
        details = body.get("message") or body.get("detail") if isinstance(body, dict) else None
        # Avoid including arbitrary server text in exceptions; it may contain the input.
        message = str(details)[:240] if isinstance(details, str) else f"HTTP {response.status_code}"
        errors = {400: BadRequestError, 401: AuthenticationError, 403: PermissionDeniedError,
                  404: NotFoundError, 409: ConflictError, 422: UnprocessableEntityError,
                  429: RateLimitError}
        cls = errors.get(response.status_code, InternalServerError if response.status_code >= 500 else APIStatusError)
        raise cls(message, response=response, body=body)

    def _normalize(self, response: httpx.Response, request_id: Optional[str] = None) -> GuardrailResult:
        self._raise_on_error(response)
        body = self._read_json(response)
        try:
            return GuardrailResult.from_api_response(body, request_id=request_id)
        except (ValueError, TypeError) as exc:
            raise ResponseFormatError(f"Invalid guardrail API response: {exc}") from exc

    def _get_sync_client(self) -> httpx.Client:
        if self._closed:
            raise RuntimeError("Guardrail client has been closed")
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self.timeout)
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._closed:
            raise RuntimeError("Guardrail client has been closed")
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    @staticmethod
    def _sync_callback(callback: Optional[Callback], result: GuardrailResult) -> None:
        if callback is None:
            return
        returned = callback(result)
        if inspect.isawaitable(returned):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(returned)
            else:
                if inspect.iscoroutine(returned):
                    returned.close()
                raise RuntimeError("Use await guard.ascan(...) when callback is async in an event loop")

    @staticmethod
    async def _async_callback(callback: Optional[Callback], result: GuardrailResult) -> None:
        if callback is not None:
            returned = callback(result)
            if inspect.isawaitable(returned):
                await returned

    def analyze(
        self,
        request: Union[AnalyzePromptRequest, Mapping[str, Any], BaseModel],
        *,
        is_async: bool = False,
        callback: Optional[Callback] = None,
    ) -> Union[GuardrailResult, Awaitable[GuardrailResult]]:
        """Post a fully specified incoming API payload as one request."""
        body = self._body(request)
        if is_async:
            return self.aanalyze(body, callback=callback)
        response = self._get_sync_client().post(self._url(), json=body, headers=self._headers())
        result = self._normalize(response, (body.get("metadata") or {}).get("request_id"))
        self._sync_callback(callback, result)
        return result

    async def aanalyze(
        self, request: Union[AnalyzePromptRequest, Mapping[str, Any], BaseModel],
        *, callback: Optional[Callback] = None,
    ) -> GuardrailResult:
        body = self._body(request)
        response = await self._get_async_client().post(self._url(), json=body, headers=self._headers())
        result = self._normalize(response, (body.get("metadata") or {}).get("request_id"))
        await self._async_callback(callback, result)
        return result

    def scan(
        self, prompt: str, *,
        config: Optional[Union[RequestConfig, Mapping[str, Any]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        guards: Optional[Sequence[Any]] = None,
        is_async: bool = False,
        callback: Optional[Callback] = None,
    ) -> Union[GuardrailResult, Awaitable[GuardrailResult]]:
        """Evaluate a text. Use ``await guard.scan(..., is_async=True)`` in async code."""
        body = self.build_request(prompt, guards=guards, config=config, metadata=metadata)
        return self.analyze(body, is_async=is_async, callback=callback)

    async def ascan(
        self, prompt: str, *,
        config: Optional[Union[RequestConfig, Mapping[str, Any]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        guards: Optional[Sequence[Any]] = None,
        callback: Optional[Callback] = None,
    ) -> GuardrailResult:
        body = self.build_request(prompt, guards=guards, config=config, metadata=metadata)
        return await self.aanalyze(body, callback=callback)

    def get_available_guardrails(self, endpoint: str = "/scanners") -> Dict[str, Any]:
        """Fetch the remote guardrail catalog (default: existing /scanners route)."""
        response = self._get_sync_client().get(self._url(endpoint), headers=self._headers())
        self._raise_on_error(response)
        body = self._read_json(response)
        if not isinstance(body, dict):
            raise ResponseFormatError("Guardrail discovery endpoint must return a JSON object")
        return body

    async def aget_available_guardrails(self, endpoint: str = "/scanners") -> Dict[str, Any]:
        response = await self._get_async_client().get(self._url(endpoint), headers=self._headers())
        self._raise_on_error(response)
        body = self._read_json(response)
        if not isinstance(body, dict):
            raise ResponseFormatError("Guardrail discovery endpoint must return a JSON object")
        return body

    get_available_scanners = get_available_guardrails

    def scan_images(
        self, files: Sequence[str], *, prompt: str = "",
        guards: Optional[Sequence[Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        config: Optional[Mapping[str, Any]] = None,
        endpoint: str = "/guard/image-input",
        callback: Optional[Callback] = None,
    ) -> GuardrailResult:
        """Compatibility-only image upload using the original multipart endpoint.

        Image uploads are NOT part of AnalyzePromptRequest and are not sent by
        ``scan`` or ``analyze``. Only use this method when the backend still
        provides the legacy ``/guard/image-input`` route.
        """
        if not files:
            raise ValueError("At least one image path is required")
        # The legacy image endpoint permits an empty associated text; the new
        # AnalyzePromptRequest model does not, so build the multipart metadata
        # explicitly from configured scanners.
        items = [self._to_use(item).model_dump(mode="json") for item in
                 (self.guardrails if guards is None else guards)]
        if not items:
            raise ValueError("At least one guardrail must be configured")
        cfg = {"fail_fast": self.fail_fast}
        if self.PROJECT_ID is not None:
            cfg["project_id"] = self.PROJECT_ID
        if self.cache is not None:
            cfg["cache"] = dict(self.cache)
        cfg.update(dict(config or {}))
        meta = {**self.default_metadata, **dict(metadata or {})}
        body = {"prompt": prompt, "config": cfg, "use": items, "metadata": meta or None}
        with ExitStack() as stack:
            attached = []
            for filename in dict.fromkeys(files):
                path = Path(filename)
                if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                    raise ValueError("Image files must be existing PNG/JPEG paths")
                mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
                attached.append(("images", (path.name, stack.enter_context(path.open("rb")), mime)))
            r = self._get_sync_client().post(self._url(endpoint),
                                             data={"metadata": json.dumps(body)},
                                             files=attached,
                                             headers={"x-api-key": self.API_KEY, "Accept": "application/json"})
            result = self._normalize(r, meta.get("request_id"))
        self._sync_callback(callback, result)
        return result

    def fetch_image_results(
        self, image_file_names: Sequence[str], download_dir: str,
        endpoint: str = "/guard/files",
    ) -> List[str]:
        """Download legacy processed-image outputs; rejects traversal filenames."""
        if not image_file_names:
            raise ValueError("At least one image file name is required")
        destination = Path(download_dir)
        destination.mkdir(parents=True, exist_ok=True)
        paths = []
        for image_name in image_file_names:
            if not isinstance(image_name, str) or Path(image_name).name != image_name or image_name in {".", ".."}:
                raise ValueError("Image names must be plain file basenames")
            r = self._get_sync_client().post(self._url(endpoint),
                 json={"project_id": self.PROJECT_ID, "file_name": image_name},
                 headers=self._headers())
            self._raise_on_error(r)
            target = destination / image_name
            target.write_bytes(r.content)
            paths.append(str(target))
        return paths

    def close(self) -> None:
        if self._owns_sync and self._sync_client is not None:
            self._sync_client.close()
        self._closed = True

    async def aclose(self) -> None:
        if self._owns_async and self._async_client is not None:
            await self._async_client.aclose()
        self.close()

    def __enter__(self) -> "Guardrail":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    async def __aenter__(self) -> "Guardrail":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        await self.aclose()


# Import aliases for older installations; the documented public API is Guardrail.
Guard = Guardrail
InputGuard = Guardrail
OutputGuard = Guardrail
ScannerResult = GuardrailResult

__all__ = ["Guardrail", "Guard", "InputGuard", "OutputGuard", "ScannerResult", "GuardrailResult", "ResponseFormatError"]
