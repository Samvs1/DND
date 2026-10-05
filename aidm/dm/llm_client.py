"""The ONE LLM client (SPEC 2.3, 4 DeepSeek, 6.1): validated tool calls, structured output, streams.

Every method returns a typed `LlmFailure` instead of raising, so callers always fall back
(SPEC 6.8). Each provider attempt is logged to `logs/llm.jsonl` (`aidm.dm.llm_log`) and counted
in `totals` (host panel).

Public API:
- `LlmClient(backend, settings, mode, log=None)`:
  - `mode`, `available` (False in DISABLED mode), `model_for(role)`, `totals`, `model_warnings`.
  - `discover_models()`: lists the provider models once (LIVE only) and resolves the role ids
    with `aidm.dm.llm_settings.resolve_models`, logging a warning for a missing default.
  - `aclose()`: closes the transport (M4.8: the live run showed the SDK's HTTP pool otherwise
    closes after the event loop, "Event loop is closed"); call it at shutdown.
  - `call_tools(messages, tools, role, *, tool_choice, max_tokens, max_retries, player_text,
    require_call) -> ToolCallResult | LlmFailure`: every call is parsed and validated against
    its tool model; an invalid or truncated answer is retried (bounded) with the validation
    errors fed back as a message; truncation doubles `max_tokens` (up to the cap). Structured
    calls use at least `settings.structured_max_tokens` (4000). Empty content is fine.
    Timeouts and transport errors are not retried (the turn falls back instead of stalling).
  - `structured(messages, schema, role, *, fallback, player_text) -> T | LlmFailure`: forces a
    single `submit_result` tool whose arguments are `schema`; on exhaustion returns `fallback`
    when given, else the `LlmFailure`.
  - `stream_text(messages, role, *, max_tokens, player_text) -> TextStream`.
- `TextStream`: async iterator of text chunks; afterwards `text` is the assembled prose and
  `failure` is set on timeout (idle or total), transport error or an empty answer.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

from pydantic import BaseModel

from aidm.dm.llm_backend import (
    BackendError,
    BackendTimeout,
    Completion,
    CompletionRequest,
    LlmBackend,
    Message,
)
from aidm.dm.llm_log import LlmCallLog, LlmCallRecord, hash_player_text
from aidm.dm.llm_settings import LlmSettings, ModelChoice, resolve_models
from aidm.dm.llm_types import (
    FailureReason,
    LlmFailure,
    LlmMode,
    LlmRole,
    TokenTotals,
    ToolCallResult,
    ToolDef,
    tool_param,
)
from aidm.dm.llm_validate import feedback_message, validate_tool_calls

_LOG = logging.getLogger(__name__)
STRUCTURED_TOOL = "submit_result"


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _hash(player_text: str | None) -> str | None:
    return hash_player_text(player_text) if player_text is not None else None


class LlmClient:
    def __init__(
        self,
        backend: LlmBackend,
        settings: LlmSettings,
        mode: LlmMode,
        log: LlmCallLog | None = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.mode = mode
        self.log = log if log is not None else LlmCallLog(settings.log_path)
        self.totals = TokenTotals()
        self.model_warnings: tuple[str, ...] = ()
        self._models = {LlmRole.FAST: settings.model_fast, LlmRole.QUALITY: settings.model_quality}

    async def aclose(self) -> None:
        await self.backend.aclose()

    @property
    def available(self) -> bool:
        return self.mode is not LlmMode.DISABLED

    def model_for(self, role: LlmRole) -> str:
        return self._models[role]

    async def discover_models(self) -> ModelChoice:
        available: list[str] = []
        if self.mode is LlmMode.LIVE:
            try:
                available = await asyncio.wait_for(
                    self.backend.list_models(), self.settings.timeout_s
                )
            except (TimeoutError, BackendTimeout, BackendError) as exc:
                _LOG.warning("model discovery failed (%s); keeping configured ids", exc)
        choice = resolve_models(
            available, self._models[LlmRole.FAST], self._models[LlmRole.QUALITY]
        )
        for warning in choice.warnings:
            _LOG.warning(warning)
        self._models = {LlmRole.FAST: choice.fast, LlmRole.QUALITY: choice.quality}
        self.model_warnings = choice.warnings
        return choice

    def record_call(
        self,
        kind: str,
        role: LlmRole,
        latency_ms: int,
        outcome: str,
        attempt: int,
        usage: tuple[int, int] = (0, 0),
        player_hash: str | None = None,
    ) -> None:
        failed = outcome != "ok"
        self.totals.add(role, usage[0], usage[1], failed=failed)
        self.log.write(
            LlmCallRecord(
                kind=kind,
                role=role.value,
                model=self._models[role],
                latency_ms=latency_ms,
                outcome=outcome,
                attempt=attempt,
                prompt_tokens=usage[0],
                completion_tokens=usage[1],
                player_text_hash=player_hash,
            )
        )

    async def _send(self, request: CompletionRequest) -> Completion | LlmFailure:
        try:
            return await asyncio.wait_for(self.backend.complete(request), self.settings.timeout_s)
        except (TimeoutError, BackendTimeout):
            return LlmFailure(FailureReason.TIMEOUT, "provider timed out")
        except BackendError as exc:
            return LlmFailure(FailureReason.TRANSPORT, exc.kind)

    async def call_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDef],
        role: LlmRole = LlmRole.FAST,
        *,
        tool_choice: str = "auto",
        max_tokens: int | None = None,
        max_retries: int | None = None,
        player_text: str | None = None,
        require_call: bool = False,
    ) -> ToolCallResult | LlmFailure:
        if not self.available:
            return LlmFailure(FailureReason.DISABLED, "llm disabled")
        by_name = {t.name: t for t in tools}
        params = [tool_param(t) for t in tools]
        budget = max(max_tokens or 0, self.settings.structured_max_tokens)
        retries = self.settings.max_retries if max_retries is None else max_retries
        convo = list(messages)
        phash = _hash(player_text)
        errors: tuple[str, ...] = ()
        for attempt in range(1, retries + 2):
            request = CompletionRequest(
                self._models[role], convo, params, tool_choice, max_tokens=budget
            )
            start = time.perf_counter()
            sent = await self._send(request)
            if isinstance(sent, LlmFailure):
                self.record_call(
                    "tools", role, _ms(start), sent.reason.value, attempt, (0, 0), phash
                )
                return LlmFailure(sent.reason, sent.detail, attempt)
            check = validate_tool_calls(sent, by_name)
            errors = check.errors
            if check.ok and require_call and not check.calls:
                errors = ("no tool was called; call one of the listed tools",)
            outcome = "ok" if not errors else ("truncated" if check.truncated else "invalid")
            usage = (sent.prompt_tokens, sent.completion_tokens)
            self.record_call("tools", role, _ms(start), outcome, attempt, usage, phash)
            if not errors:
                return ToolCallResult(check.calls, sent.content, attempt)
            if check.truncated:
                budget = min(budget * 2, self.settings.max_tokens_cap)
            convo = [*convo, feedback_message(errors, truncated=check.truncated)]
        return LlmFailure(FailureReason.VALIDATION, "; ".join(errors), retries + 1)

    async def structured[T: BaseModel](
        self,
        messages: Sequence[Message],
        schema: type[T],
        role: LlmRole = LlmRole.FAST,
        *,
        fallback: T | None = None,
        player_text: str | None = None,
    ) -> T | LlmFailure:
        tool = ToolDef(STRUCTURED_TOOL, schema.__doc__ or "Return the result.", schema)
        result = await self.call_tools(
            messages,
            [tool],
            role,
            tool_choice=STRUCTURED_TOOL,
            player_text=player_text,
            require_call=True,
        )
        if isinstance(result, ToolCallResult):
            args = result.calls[0].args
            if isinstance(args, schema):
                return args
            result = LlmFailure(FailureReason.VALIDATION, "wrong result type", result.attempts)
        return fallback if fallback is not None else result

    def stream_text(
        self,
        messages: Sequence[Message],
        role: LlmRole = LlmRole.QUALITY,
        *,
        max_tokens: int = 700,
        player_text: str | None = None,
    ) -> "TextStream":
        request = CompletionRequest(self._models[role], list(messages), max_tokens=max_tokens)
        return TextStream(self, request, role, _hash(player_text))


class TextStream:
    def __init__(
        self, client: LlmClient, request: CompletionRequest, role: LlmRole, phash: str | None
    ) -> None:
        self._client = client
        self._request = request
        self._role = role
        self._phash = phash
        self.parts: list[str] = []
        self.failure: LlmFailure | None = None

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def __aiter__(self) -> AsyncIterator[str]:
        return self._run()

    async def _run(self) -> AsyncIterator[str]:
        client = self._client
        if not client.available:
            self.failure = LlmFailure(FailureReason.DISABLED, "llm disabled")
            return
        start = time.perf_counter()
        usage = [0, 0]
        try:
            async for text in self._chunks(usage):
                self.parts.append(text)
                yield text
        except (TimeoutError, BackendTimeout):
            self.failure = LlmFailure(FailureReason.TIMEOUT, "stream timed out", 1)
        except BackendError as exc:
            self.failure = LlmFailure(FailureReason.TRANSPORT, exc.kind, 1)
        if self.failure is None and not self.text.strip():
            self.failure = LlmFailure(FailureReason.EMPTY, "empty narration", 1)
        outcome = "ok" if self.failure is None else self.failure.reason.value
        client.record_call(
            "stream", self._role, _ms(start), outcome, 1, (usage[0], usage[1]), self._phash
        )

    async def _chunks(self, usage: list[int]) -> AsyncIterator[str]:
        settings = self._client.settings
        deadline = time.perf_counter() + settings.timeout_s
        it = aiter(self._client.backend.stream(self._request))
        try:
            while True:
                wait = min(settings.stream_idle_timeout_s, deadline - time.perf_counter())
                if wait <= 0:
                    raise TimeoutError
                try:
                    chunk = await asyncio.wait_for(anext(it), wait)
                except StopAsyncIteration:
                    return
                if chunk.prompt_tokens is not None:
                    usage[0] = chunk.prompt_tokens
                if chunk.completion_tokens is not None:
                    usage[1] = chunk.completion_tokens
                if chunk.text:
                    yield chunk.text
        finally:
            closer: Any = getattr(it, "aclose", None)
            if closer is not None:
                await closer()
