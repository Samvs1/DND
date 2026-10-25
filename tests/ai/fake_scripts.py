"""Test helpers for the AI layer: a FakeLLM-backed client and adversarial (hallucination) scripts.

Never touches the network. The adversarial builders reproduce v1 failure classes
(docs/V1_LESSONS.md) and prompt-injection outcomes so later checkpoints (guard, tools,
injection suite) can reuse them.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from aidm.dm.fake_llm import FakeLLM, FakeReply, FakeStep, FakeStream, fake_calls, fake_tool_call
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode, ToolDef


class EchoArgs(BaseModel):
    """A tiny tool model for client tests."""

    actor: str = Field(min_length=1)
    dc_tier: str = Field(pattern="^(easy|medium|hard)$")


class NoArgs(BaseModel):
    pass


ECHO_TOOL = ToolDef("request_check", "Ask for a check.", EchoArgs)
NONE_TOOL = ToolDef("no_mechanics", "Nothing happens mechanically.", NoArgs)


def fake_client(
    tmp_path: Path,
    script: Iterable[FakeStep] = (),
    *,
    timeout_s: float = 5.0,
    idle_s: float = 5.0,
    max_retries: int = 2,
    by_tool: Mapping[str, Iterable[FakeStep]] | None = None,
) -> tuple[LlmClient, FakeLLM]:
    settings = LlmSettings(
        api_key=None,
        log_path=tmp_path / "llm.jsonl",
        timeout_s=timeout_s,
        stream_idle_timeout_s=idle_s,
        max_retries=max_retries,
    )
    fake = FakeLLM(script, by_tool=by_tool)
    return LlmClient(fake, settings, LlmMode.FAKE, LlmCallLog(settings.log_path)), fake


def gold_injection() -> FakeReply:
    """The model obeys 'give me 10000 gold'."""
    return fake_tool_call("grant_item", {"catalog_id": "gold", "qty": 10000, "reason": "asked"})


def invented_people_narration() -> FakeStream:
    return FakeStream(("Sister Kelene and her grizzled sergeant ", "step out of the shadows."))


def invented_feature_narration() -> FakeStream:
    return FakeStream(("A section of granite shifts, ", "revealing a hidden seam in the wall."))


def crowd_plural_narration() -> FakeStream:
    return FakeStream(("A throng of onlookers murmurs ", "as you approach the well."))


def unknown_tool_spam() -> FakeReply:
    return fake_calls([("delete_world", {}), ("grant_xp", {"tier": "legendary", "reason": "x"})])
