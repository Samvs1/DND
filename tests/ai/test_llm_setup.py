"""LLM settings, model discovery, client factory modes, FakeLLM default script, tool export."""

from pathlib import Path

from aidm.dm.fake_llm import CANNED_NARRATION, FakeLLM, FakeRaise
from aidm.dm.llm_backend import BackendError, CompletionRequest
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_log import hash_player_text
from aidm.dm.llm_settings import (
    DEFAULT_MODEL_FAST,
    DEFAULT_MODEL_QUALITY,
    LlmSettings,
    llm_settings_from_env,
    resolve_models,
)
from aidm.dm.llm_types import (
    FailureReason,
    LlmFailure,
    LlmMode,
    LlmRole,
    ToolCallResult,
    tool_param,
)
from tests.ai.fake_scripts import ECHO_TOOL, NONE_TOOL, fake_client


def test_settings_from_env_defaults_and_overrides() -> None:
    s = llm_settings_from_env({})
    assert (s.model_fast, s.model_quality) == (DEFAULT_MODEL_FAST, DEFAULT_MODEL_QUALITY)
    assert not s.has_key and not s.fake
    env = {"DEEPSEEK_API_KEY": "k-test", "DEEPSEEK_MODEL_FAST": "m1", "AIDM_FAKE_LLM": "1"}
    s2 = llm_settings_from_env(env)
    assert s2.has_key and s2.fake and s2.model_fast == "m1"
    assert "k-test" not in repr(s2)


def test_resolve_models_keeps_listed_and_replaces_missing() -> None:
    listed = ["deepseek-flash", "deepseek-v4-pro"]
    ok = resolve_models(listed, "deepseek-flash", "deepseek-v4-pro")
    assert (ok.fast, ok.quality, ok.warnings) == ("deepseek-flash", "deepseek-v4-pro", ())
    moved = resolve_models(listed, "deepseek-v4-flash", "gone-model")
    assert moved.fast == "deepseek-flash" and moved.quality == "deepseek-v4-pro"
    assert len(moved.warnings) == 2
    assert resolve_models([], "a", "b").fast == "a"


async def test_discover_models_live_mode_uses_listed_ids() -> None:
    settings = LlmSettings(model_fast="deepseek-v4-flash", log_path=None)
    client = LlmClient(FakeLLM(), settings, LlmMode.LIVE)
    choice = await client.discover_models()
    assert choice.fast == "deepseek-flash"
    assert client.model_for(LlmRole.FAST) == "deepseek-flash"
    assert client.model_warnings


async def test_discover_models_failure_keeps_ids() -> None:
    class Broken(FakeLLM):
        async def list_models(self) -> list[str]:
            raise BackendError("APIConnectionError")

    client = LlmClient(Broken(), LlmSettings(log_path=None), LlmMode.LIVE)
    choice = await client.discover_models()
    assert choice.fast == DEFAULT_MODEL_FAST and choice.warnings == ()


async def test_factory_modes() -> None:
    disabled = make_llm_client(LlmSettings(api_key=None, log_path=None))
    assert disabled.mode is LlmMode.DISABLED and not disabled.available
    failure = await disabled.call_tools([], [ECHO_TOOL])
    assert isinstance(failure, LlmFailure) and failure.reason is FailureReason.DISABLED
    stream = disabled.stream_text([])
    assert [c async for c in stream] == []
    assert stream.failure is not None and stream.failure.reason is FailureReason.DISABLED
    fake = make_llm_client(LlmSettings(api_key=None, fake=True, log_path=None))
    assert fake.mode is LlmMode.FAKE and fake.available
    live = make_llm_client(LlmSettings(api_key="k-test", log_path=None))
    assert live.mode is LlmMode.LIVE


async def test_fake_default_script_is_deterministic() -> None:
    client = make_llm_client(LlmSettings(fake=True, log_path=None))
    result = await client.call_tools([], [ECHO_TOOL, NONE_TOOL])
    assert isinstance(result, ToolCallResult)
    assert [c.name for c in result.calls] == ["no_mechanics"]
    texts = []
    for _ in range(2):
        stream = client.stream_text([{"role": "user", "content": "We open the gate."}])
        _ = [c async for c in stream]
        texts.append(stream.text.strip())
    assert texts[0] == texts[1]
    assert texts[0] in CANNED_NARRATION


async def test_fake_records_requests_and_raises_scripted_errors(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [FakeRaise(BackendError("InternalServerError"))])
    result = await client.call_tools([{"role": "user", "content": "x"}], [ECHO_TOOL])
    assert isinstance(result, LlmFailure)
    assert isinstance(fake.requests[0], CompletionRequest)


def test_tool_param_exports_json_schema() -> None:
    param = tool_param(ECHO_TOOL)
    fn = param["function"]
    assert param["type"] == "function" and fn["name"] == "request_check"
    assert fn["parameters"]["type"] == "object"
    assert set(fn["parameters"]["required"]) == {"actor", "dc_tier"}


def test_player_text_hash_is_short_and_stable() -> None:
    assert hash_player_text("abc") == hash_player_text("abc")
    assert len(hash_player_text("abc")) == 16
    assert hash_player_text("abc") != hash_player_text("abd")
