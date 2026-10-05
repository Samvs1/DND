"""The real transport: DeepSeek through the `openai` SDK (`AsyncOpenAI`, base URL api.deepseek.com).

Verified DeepSeek facts (docs/DECISIONS.md M4.1): thinking mode is ON by default and does not
support `tool_choice`, so every call sends `extra_body={"thinking": {"type": "disabled"}}`;
JSON mode is `response_format={"type": "json_object"}`; streaming usage needs
`stream_options={"include_usage": True}`; tool calls may come with empty `content`.

Public API: `OpenAIBackend(api_key, base_url, timeout_s)` implementing
`aidm.dm.llm_backend.LlmBackend`. SDK exceptions are mapped to `BackendTimeout` /
`BackendError(kind)` with the exception class name only (no request data, no key).
"""

from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from aidm.dm.llm_backend import (
    BackendError,
    BackendTimeout,
    Completion,
    CompletionRequest,
    RawToolCall,
    StreamChunk,
)

_NO_THINKING: dict[str, Any] = {"thinking": {"type": "disabled"}}


def _kwargs(request: CompletionRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": request.model,
        "messages": request.messages,
        "max_tokens": request.max_tokens,
        "extra_body": _NO_THINKING,
    }
    if request.tools:
        kwargs["tools"] = request.tools
        choice = request.tool_choice or "auto"
        if choice in {"auto", "required", "none"}:
            kwargs["tool_choice"] = choice
        else:
            kwargs["tool_choice"] = {"type": "function", "function": {"name": choice}}
    if request.json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _map_error(exc: Exception) -> Exception:
    if isinstance(exc, openai.APITimeoutError):
        return BackendTimeout()
    return BackendError(type(exc).__name__)


def _tool_calls(message: Any) -> tuple[RawToolCall, ...]:
    out: list[RawToolCall] = []
    for call in message.tool_calls or ():
        fn = getattr(call, "function", None)
        if fn is None:
            continue
        out.append(RawToolCall(id=call.id, name=fn.name, arguments=fn.arguments or ""))
    return tuple(out)


class OpenAIBackend:
    def __init__(self, api_key: str, base_url: str, timeout_s: float) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=0
        )

    async def complete(self, request: CompletionRequest) -> Completion:
        try:
            resp: Any = await self._client.chat.completions.create(**_kwargs(request))
        except openai.OpenAIError as exc:
            raise _map_error(exc) from None
        if not resp.choices:
            raise BackendError("no_choices")
        choice = resp.choices[0]
        usage = resp.usage
        return Completion(
            content=choice.message.content or "",
            tool_calls=_tool_calls(choice.message),
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        kwargs = _kwargs(request)
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        try:
            stream: Any = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                for choice in chunk.choices or ():
                    text = getattr(choice.delta, "content", None)
                    if text:
                        yield StreamChunk(text=text)
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    yield StreamChunk(
                        prompt_tokens=usage.prompt_tokens or 0,
                        completion_tokens=usage.completion_tokens or 0,
                    )
        except openai.OpenAIError as exc:
            raise _map_error(exc) from None

    async def list_models(self) -> list[str]:
        try:
            page: Any = await self._client.models.list()
        except openai.OpenAIError as exc:
            raise _map_error(exc) from None
        return [m.id for m in page.data]

    async def aclose(self) -> None:
        await self._client.close()
