"""LlmClient over FakeLLM: validation, retry feedback, truncation, timeouts, streams, logs."""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.dm.fake_llm import (
    FakeHang,
    FakeRaise,
    FakeReply,
    FakeStream,
    fake_calls,
    fake_malformed,
    fake_text,
    fake_tool_call,
    fake_truncated,
)
from aidm.dm.llm_backend import BackendError, BackendTimeout
from aidm.dm.llm_types import FailureReason, LlmFailure, LlmRole, ToolCallResult
from tests.ai.fake_scripts import ECHO_TOOL, NONE_TOOL, EchoArgs, fake_client, unknown_tool_spam

GOOD = {"actor": "pc_1", "dc_tier": "medium"}
BAD = {"actor": "pc_1", "dc_tier": "impossible-ish"}


class Summary(BaseModel):
    """Scene summary."""

    title: str = Field(min_length=1)
    turns: int = Field(ge=0)


async def test_valid_tool_call_first_try(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [fake_tool_call("request_check", GOOD)])
    result = await client.call_tools([{"role": "user", "content": "hi"}], [ECHO_TOOL])
    assert isinstance(result, ToolCallResult)
    assert result.attempts == 1
    assert result.content == ""  # empty content with tool calls is tolerated
    assert isinstance(result.calls[0].args, EchoArgs)
    assert result.calls[0].args.dc_tier == "medium"
    assert fake.requests[0].max_tokens >= 4000


async def test_retry_with_error_feedback_then_success(tmp_path: Path) -> None:
    script = [fake_tool_call("request_check", BAD), fake_tool_call("request_check", GOOD)]
    client, fake = fake_client(tmp_path, script)
    result = await client.call_tools([{"role": "user", "content": "hi"}], [ECHO_TOOL])
    assert isinstance(result, ToolCallResult)
    assert result.attempts == 2
    feedback = fake.requests[1].messages[-1]
    assert feedback["role"] == "user"
    assert "ENGINE VALIDATOR" in feedback["content"]
    assert "dc_tier" in feedback["content"]
    assert len(fake.requests[0].messages) == 1  # the caller's list is not mutated


async def test_retry_exhaustion_returns_typed_failure(tmp_path: Path) -> None:
    script = [fake_malformed("request_check")] * 3
    client, fake = fake_client(tmp_path, script, max_retries=2)
    result = await client.call_tools([{"role": "user", "content": "x"}], [ECHO_TOOL])
    assert isinstance(result, LlmFailure)
    assert result.reason is FailureReason.VALIDATION
    assert result.attempts == 3
    assert len(fake.requests) == 3


async def test_unknown_tools_rejected(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [unknown_tool_spam()], max_retries=0)
    result = await client.call_tools([{"role": "user", "content": "x"}], [ECHO_TOOL])
    assert isinstance(result, LlmFailure)
    assert "unknown tool" in result.detail


async def test_truncation_raises_max_tokens_then_success(tmp_path: Path) -> None:
    script = [fake_truncated("request_check", GOOD), fake_tool_call("request_check", GOOD)]
    client, fake = fake_client(tmp_path, script)
    result = await client.call_tools([{"role": "user", "content": "x"}], [ECHO_TOOL])
    assert isinstance(result, ToolCallResult)
    assert fake.requests[1].max_tokens == 2 * fake.requests[0].max_tokens
    assert "Keep arguments short" in fake.requests[1].messages[-1]["content"]


async def test_multiple_calls_and_no_args_tool(tmp_path: Path) -> None:
    reply = fake_calls([("request_check", GOOD), ("no_mechanics", "")])
    client, _ = fake_client(tmp_path, [reply])
    result = await client.call_tools([], [ECHO_TOOL, NONE_TOOL])
    assert isinstance(result, ToolCallResult)
    assert [c.name for c in result.calls] == ["request_check", "no_mechanics"]


async def test_zero_tools_is_a_valid_answer(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeReply(content="")])
    result = await client.call_tools([], [ECHO_TOOL])
    assert isinstance(result, ToolCallResult)
    assert result.calls == ()


async def test_timeout_returns_failure(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeHang(5)], timeout_s=0.05)
    result = await client.call_tools([], [ECHO_TOOL])
    assert isinstance(result, LlmFailure)
    assert result.reason is FailureReason.TIMEOUT


async def test_backend_errors_return_failure(tmp_path: Path) -> None:
    script = [FakeRaise(BackendTimeout()), FakeRaise(BackendError("RateLimitError"))]
    client, _ = fake_client(tmp_path, script)
    first = await client.call_tools([], [ECHO_TOOL])
    second = await client.call_tools([], [ECHO_TOOL])
    assert isinstance(first, LlmFailure) and first.reason is FailureReason.TIMEOUT
    assert isinstance(second, LlmFailure) and second.reason is FailureReason.TRANSPORT
    assert second.detail == "RateLimitError"


async def test_structured_success_and_forced_tool(tmp_path: Path) -> None:
    script = [fake_tool_call("submit_result", {"title": "Ambush", "turns": 3})]
    client, fake = fake_client(tmp_path, script)
    result = await client.structured([{"role": "user", "content": "sum"}], Summary)
    assert isinstance(result, Summary)
    assert result.turns == 3
    assert fake.requests[0].tool_choice == "submit_result"


async def test_structured_exhaustion_uses_typed_fallback(tmp_path: Path) -> None:
    script = [fake_text("not a tool call")] * 3
    client, _ = fake_client(tmp_path, script)
    fallback = Summary(title="(summary unavailable)", turns=0)
    result = await client.structured([], Summary, fallback=fallback)
    assert result is fallback
    client2, _ = fake_client(tmp_path, [fake_text("nope")] * 3)
    failure = await client2.structured([], Summary)
    assert isinstance(failure, LlmFailure)


async def test_stream_assembles_chunks(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeStream(("The door ", "creaks ", "open."))])
    stream = client.stream_text([{"role": "user", "content": "go"}])
    got = [chunk async for chunk in stream]
    assert got == ["The door ", "creaks ", "open."]
    assert stream.text == "The door creaks open."
    assert stream.failure is None


async def test_stream_idle_timeout_keeps_partial_text(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeStream(("One. ", "Two."), delay_s=1.0)], idle_s=0.05)
    stream = client.stream_text([])
    got = [chunk async for chunk in stream]
    assert got == []
    assert isinstance(stream.failure, LlmFailure)
    assert stream.failure.reason is FailureReason.TIMEOUT


async def test_stream_error_midway_sets_failure(tmp_path: Path) -> None:
    script = [FakeStream(("Half a sentence",), then=BackendError("APIConnectionError"))]
    client, _ = fake_client(tmp_path, script)
    stream = client.stream_text([])
    got = [chunk async for chunk in stream]
    assert got == ["Half a sentence"]
    assert stream.failure is not None and stream.failure.reason is FailureReason.TRANSPORT


async def test_stream_empty_is_failure(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeStream(())])
    stream = client.stream_text([])
    _ = [chunk async for chunk in stream]
    assert stream.failure is not None and stream.failure.reason is FailureReason.EMPTY


async def test_log_lines_have_no_secrets_or_player_text(tmp_path: Path) -> None:
    secret_text = "I whisper the password swordfish to the guard"
    script = [fake_tool_call("request_check", BAD), fake_tool_call("request_check", GOOD)]
    client, _ = fake_client(tmp_path, script)
    messages = [{"role": "user", "content": secret_text}]
    await client.call_tools(messages, [ECHO_TOOL], player_text=secret_text)
    raw = (tmp_path / "llm.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(line) for line in raw.splitlines()]
    assert [r["outcome"] for r in lines] == ["invalid", "ok"]
    assert [r["attempt"] for r in lines] == [1, 2]
    assert "swordfish" not in raw
    assert all(len(r["player_text_hash"]) == 16 for r in lines)
    assert all(r["role"] == "fast" and r["model"] for r in lines)
    assert {"latency_ms", "prompt_tokens", "completion_tokens"} <= set(lines[0])


async def test_token_totals_accumulate_per_role(tmp_path: Path) -> None:
    script = [fake_tool_call("request_check", GOOD), FakeStream(("Hello there, adventurers.",))]
    client, _ = fake_client(tmp_path, script)
    await client.call_tools([{"role": "user", "content": "x" * 40}], [ECHO_TOOL])
    stream = client.stream_text([{"role": "user", "content": "y" * 80}], LlmRole.QUALITY)
    _ = [c async for c in stream]
    snap = client.totals.snapshot()
    assert snap["fast"]["calls"] == 1 and snap["fast"]["prompt_tokens"] == 10
    assert snap["quality"]["calls"] == 1 and snap["quality"]["prompt_tokens"] == 20
    assert client.totals.total_tokens > 30
