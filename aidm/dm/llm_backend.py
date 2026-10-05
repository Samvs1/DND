"""Transport layer of the LLM client: the swappable backend protocol and its wire types.

`aidm.dm.llm_client.LlmClient` talks to exactly one `LlmBackend`. The real one is
`aidm.dm.openai_backend.OpenAIBackend` (DeepSeek through the `openai` SDK); tests and the
`AIDM_FAKE_LLM=1` server mode use `aidm.dm.fake_llm.FakeLLM`; a missing key uses
`DisabledBackend`. Backends never validate or retry; the client does.

Public API:
- `CompletionRequest(model, messages, tools, tool_choice, json_mode, max_tokens)`: one chat call.
  `messages` are OpenAI-format dicts; `tools` are OpenAI `tools` entries; `tool_choice` is
  "auto" / "required" / "none" or a function name (forced).
- `RawToolCall(id, name, arguments)`: one tool call as returned (`arguments` is the raw JSON text).
- `Completion(content, tool_calls, finish_reason, prompt_tokens, completion_tokens)`.
- `StreamChunk(text, prompt_tokens, completion_tokens)`: one streamed delta; the usage fields are
  set only on the final usage chunk.
- `BackendTimeout`, `BackendError(kind)`: the only exceptions a backend may raise.
- `LlmBackend` (Protocol): `complete(request)`, `stream(request)`, `list_models()`.
- `DisabledBackend`: every call raises `BackendError("disabled")` (no key configured).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

type Message = dict[str, Any]


@dataclass(frozen=True)
class CompletionRequest:
    model: str
    messages: list[Message]
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = None
    json_mode: bool = False
    max_tokens: int = 1024


@dataclass(frozen=True)
class RawToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Completion:
    content: str = ""
    tool_calls: tuple[RawToolCall, ...] = ()
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class StreamChunk:
    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class BackendTimeout(Exception):
    """The provider did not answer in time."""


@dataclass
class BackendError(Exception):
    """Any other transport failure; `kind` is a short machine label (never contains secrets)."""

    kind: str
    detail: str = field(default="")

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}" if self.detail else self.kind


class LlmBackend(Protocol):
    async def complete(self, request: CompletionRequest) -> Completion: ...

    def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...

    async def list_models(self) -> list[str]: ...


class DisabledBackend:
    """Backend for the no-key mode: every call fails fast so callers use their fallbacks."""

    async def complete(self, request: CompletionRequest) -> Completion:
        raise BackendError("disabled", "no DeepSeek key configured")

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        raise BackendError("disabled", "no DeepSeek key configured")
        yield StreamChunk()  # pragma: no cover - makes this an async generator

    async def list_models(self) -> list[str]:
        return []
