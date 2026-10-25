"""FakeLLM: a deterministic, scriptable `LlmBackend` for tests and `AIDM_FAKE_LLM=1` server mode.

Each provider call (complete or stream) consumes the next scripted step; when the script is empty
the `responder` (default: `default_fake_step`) answers. Every request is recorded in `requests`
so tests can assert what the client sent (retry feedback, max_tokens, tools).

Public API:
- Steps: `FakeReply(content, tool_calls, finish_reason)`, `FakeStream(chunks, then, delay_s)`,
  `FakeHang(seconds)` (sleeps, so the client timeout fires), `FakeRaise(error)` (raises a
  backend exception: `BackendTimeout()` or `BackendError(kind)`).
- Builders: `fake_tool_call(name, args, call_id)`, `fake_calls(pairs)`, `fake_text(text)`,
  `fake_malformed(name)` (arguments are not JSON), `fake_truncated(name, args)` (JSON cut in half,
  finish_reason "length").
- `FakeStep` (the union), `default_fake_step(request)`: `no_mechanics` when offered, an empty
  `{}` call for a forced tool (callers fall back if it does not validate), and a short canned
  narration chosen by a stable hash of the last user message for text calls.
- `FakeLLM(script=(), responder=None, models=..., by_tool=None)`. M36.5: a call that forces a tool
  named in `by_tool` (e.g. `{"choose_actions": [...]}`) takes its step from that tool's own
  script, never from the main `script`; when that is empty, `TOOL_DEFAULTS` answers
  (`choose_actions`: `other` = the player's line, `default_choice_step`), so every existing
  adjudicator test keeps its own scripted steps unchanged.
"""

import asyncio
import hashlib
import html
import json
import re
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aidm.dm.context_text import PLAYER_TAG
from aidm.dm.llm_backend import (
    BackendError,
    BackendTimeout,
    Completion,
    CompletionRequest,
    RawToolCall,
    StreamChunk,
)


@dataclass(frozen=True)
class FakeReply:
    content: str = ""
    tool_calls: tuple[RawToolCall, ...] = ()
    finish_reason: str = "stop"


@dataclass(frozen=True)
class FakeStream:
    chunks: tuple[str, ...]
    then: BackendError | BackendTimeout | None = None
    delay_s: float = 0.0


@dataclass(frozen=True)
class FakeHang:
    seconds: float = 3600.0


@dataclass(frozen=True)
class FakeRaise:
    error: BackendError | BackendTimeout


type FakeStep = FakeReply | FakeStream | FakeHang | FakeRaise


def fake_tool_call(name: str, args: Mapping[str, Any] | str, call_id: str = "call_0") -> FakeReply:
    raw = args if isinstance(args, str) else json.dumps(dict(args))
    return FakeReply(tool_calls=(RawToolCall(call_id, name, raw),), finish_reason="tool_calls")


def fake_calls(pairs: Sequence[tuple[str, Mapping[str, Any] | str]]) -> FakeReply:
    calls = tuple(
        RawToolCall(f"call_{i}", name, args if isinstance(args, str) else json.dumps(dict(args)))
        for i, (name, args) in enumerate(pairs)
    )
    return FakeReply(tool_calls=calls, finish_reason="tool_calls")


def fake_text(text: str) -> FakeReply:
    return FakeReply(content=text)


def fake_malformed(name: str) -> FakeReply:
    return fake_tool_call(name, '{"actor": "pc_1", "dc_tier": medium')


def fake_truncated(name: str, args: Mapping[str, Any]) -> FakeReply:
    raw = json.dumps(dict(args))
    cut = RawToolCall("call_0", name, raw[: max(1, len(raw) // 2)])
    return FakeReply(tool_calls=(cut,), finish_reason="length")


CANNED_NARRATION = (
    "The moment passes, and the scene around you settles. Nothing new stirs for now.",
    "You take stock of your surroundings. The way ahead waits, quiet and patient.",
    "Your effort draws no answer from the world, not yet. The air feels still.",
)


def _last_user(messages: Sequence[Mapping[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def default_fake_step(request: CompletionRequest) -> FakeStep:
    if request.tools:
        names = [t["function"]["name"] for t in request.tools]
        forced = request.tool_choice not in (None, "auto", "required", "none")
        if forced and request.tool_choice in names:
            return fake_tool_call(str(request.tool_choice), {})
        if "no_mechanics" in names:
            return fake_tool_call("no_mechanics", {})
        return FakeReply()
    digest = hashlib.sha256(_last_user(request.messages).encode("utf-8")).digest()
    return fake_text(CANNED_NARRATION[digest[0] % len(CANNED_NARRATION)])


_PLAYER_LINE = re.compile(rf"<{PLAYER_TAG}[^>]*>(.*?)</{PLAYER_TAG}>", re.DOTALL)


def default_choice_step(request: CompletionRequest) -> FakeStep:
    """`choose_actions` with no script: `other` holding the player's line (the storyteller's)."""
    found = [m for msg in request.messages for m in _PLAYER_LINE.findall(str(msg.get("content")))]
    line = html.unescape(found[-1]) if found else ""
    return fake_tool_call("choose_actions", {"steps": [], "other": {"text": line, "first": False}})


TOOL_DEFAULTS: dict[str, Callable[[CompletionRequest], FakeStep]] = {
    "choose_actions": default_choice_step
}


def _forced(request: CompletionRequest) -> str | None:
    choice = request.tool_choice
    return choice if request.tools and choice not in (None, "auto", "required", "none") else None


def _tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _prompt_tokens(request: CompletionRequest) -> int:
    return sum(_tokens(str(m.get("content", ""))) for m in request.messages)


class FakeLLM:
    def __init__(
        self,
        script: Iterable[FakeStep] = (),
        responder: Callable[[CompletionRequest], FakeStep] | None = None,
        models: Sequence[str] = ("deepseek-flash", "deepseek-v4-pro"),
        by_tool: Mapping[str, Iterable[FakeStep]] | None = None,
    ) -> None:
        self.script: deque[FakeStep] = deque(script)
        self.by_tool: dict[str, deque[FakeStep]] = {
            name: deque(steps) for name, steps in (by_tool or {}).items()
        }
        self.responder = responder or default_fake_step
        self.models = list(models)
        self.requests: list[CompletionRequest] = []
        self.closed = False

    def push(self, *steps: FakeStep) -> None:
        self.script.extend(steps)

    def _next(self, request: CompletionRequest) -> FakeStep:
        self.requests.append(request)
        tool = _forced(request)
        own = self.by_tool.get(tool) if tool is not None else None
        if own:
            return own.popleft()
        if tool is not None and (own is not None or tool in TOOL_DEFAULTS):
            return TOOL_DEFAULTS.get(tool, default_fake_step)(request)
        return self.script.popleft() if self.script else self.responder(request)

    async def complete(self, request: CompletionRequest) -> Completion:
        step = self._next(request)
        if isinstance(step, FakeHang):
            await asyncio.sleep(step.seconds)
            return Completion()
        if isinstance(step, FakeRaise):
            raise step.error
        if isinstance(step, FakeStream):
            step = FakeReply(content="".join(step.chunks))
        out = step.content + "".join(c.arguments for c in step.tool_calls)
        return Completion(
            content=step.content,
            tool_calls=step.tool_calls,
            finish_reason=step.finish_reason,
            prompt_tokens=_prompt_tokens(request),
            completion_tokens=_tokens(out),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        step = self._next(request)
        if isinstance(step, FakeHang):
            await asyncio.sleep(step.seconds)
            return
        if isinstance(step, FakeRaise):
            raise step.error
        if isinstance(step, FakeReply):
            step = FakeStream(tuple(w + " " for w in step.content.split()))
        for chunk in step.chunks:
            if step.delay_s:
                await asyncio.sleep(step.delay_s)
            yield StreamChunk(text=chunk)
        if step.then is not None:
            raise step.then
        out = "".join(step.chunks)
        yield StreamChunk(prompt_tokens=_prompt_tokens(request), completion_tokens=_tokens(out))

    async def list_models(self) -> list[str]:
        return list(self.models)

    async def aclose(self) -> None:
        self.closed = True
