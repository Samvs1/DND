"""OpenAI image provider (Addendum B.2): the ONLY network the asset generator uses.

Endpoints: `models.list`, `images.generate`, `images.edit` (multi-reference input). The SDK client
is built with `max_retries=0` so every retry is a visible, budget-checked call of our own. The API
key comes from the caller (`IMAGE_API_KEY`); it is never printed, logged, stored, put in a repr or
in exception text: every SDK error is re-raised as `ProviderError` with the key (and anything
key-shaped) redacted and the original exception detached.

Public API: `OpenAIImageProvider`, `make_openai_client`.
"""

import base64
from contextlib import ExitStack
from typing import Any

from aidm.server.assetgen.provider import (
    ImageRequest,
    ImageResult,
    ImageUsage,
    ModelInfo,
    ProviderError,
    redact,
)

REQUEST_TIMEOUT_S = 180.0


def make_openai_client(api_key: str) -> Any:
    """An OpenAI SDK client with SDK-side retries disabled."""
    from openai import OpenAI

    return OpenAI(api_key=api_key, max_retries=0, timeout=REQUEST_TIMEOUT_S)


def _usage(raw: Any) -> ImageUsage:
    if raw is None:
        return ImageUsage()
    details = getattr(raw, "input_tokens_details", None)
    text = int(getattr(details, "text_tokens", 0) or 0)
    image = int(getattr(details, "image_tokens", 0) or 0)
    total_in = int(getattr(raw, "input_tokens", 0) or 0)
    if details is None:
        text = total_in
    return ImageUsage(
        text_input_tokens=text,
        image_input_tokens=image,
        output_tokens=int(getattr(raw, "output_tokens", 0) or 0),
        reported=True,
    )


class OpenAIImageProvider:
    name = "openai"

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if not api_key:
            raise ProviderError("IMAGE_API_KEY is not set")
        self._secret = api_key
        self._client = client if client is not None else make_openai_client(api_key)

    def __repr__(self) -> str:
        return "OpenAIImageProvider()"

    def _error(self, operation: str, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None)
        code = f" (HTTP {status})" if status else ""
        text = f"{operation} failed{code}: {type(exc).__name__}: {exc}"
        return ProviderError(redact(text, self._secret))

    def list_models(self) -> list[ModelInfo]:
        try:
            listed = list(self._client.models.list())
        except Exception as exc:
            raise self._error("models.list", exc) from None
        return [ModelInfo(str(m.id), int(getattr(m, "created", 0) or 0)) for m in listed]

    def _params(self, request: ImageRequest, model: str) -> dict[str, Any]:
        return {
            "model": model,
            "prompt": request.prompt,
            "size": request.size,
            "quality": request.quality,
            "background": "transparent" if request.transparent else "auto",
            "output_format": "png",
            "n": 1,
        }

    def _result(self, response: Any, model: str) -> ImageResult:
        data = getattr(response, "data", None) or []
        b64 = getattr(data[0], "b64_json", None) if data else None
        if not b64:
            raise ProviderError("the response carried no image")
        return ImageResult(base64.b64decode(b64), model, _usage(getattr(response, "usage", None)))

    def generate(self, request: ImageRequest, model: str) -> ImageResult:
        try:
            response = self._client.images.generate(**self._params(request, model))
        except Exception as exc:
            raise self._error("images.generate", exc) from None
        return self._result(response, model)

    def edit(self, request: ImageRequest, model: str) -> ImageResult:
        if not request.references:
            raise ProviderError("edit needs at least one reference image")
        try:
            with ExitStack() as stack:
                files = [stack.enter_context(p.open("rb")) for p in request.references]
                response = self._client.images.edit(image=files, **self._params(request, model))
        except Exception as exc:
            raise self._error("images.edit", exc) from None
        return self._result(response, model)
