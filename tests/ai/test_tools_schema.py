"""DM tool schemas: every SPEC 6.3 tool exists, exports a JSON schema and bounds its args."""

import random

import pytest
from pydantic import ValidationError

from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_exec import TOOL_EXECUTORS, execute_tool
from aidm.dm.tools import (
    DM_TOOLS,
    GrantItemArgs,
    IntroduceFeatureArgs,
    NoMechanicsArgs,
    dm_tools_param,
)
from tests.ai.tool_fixtures import ACTOR, REGS, party_state, tool_call

SPEC_TOOLS = [
    "request_check",
    "request_save",
    "creative_effect",
    "update_attitude",
    "reveal_secret",
    "move_party",
    "introduce_npc",
    "introduce_feature",
    "grant_item",
    "grant_xp",
    "start_encounter",
    "open_shop",
    "update_quest",
    "offer_favour",  # M23.5
    "record_fact",
    "take_item",  # M19.3
    "give_keepsake",  # M19.3
    "no_mechanics",
]


def test_every_spec_tool_has_schema_and_executor() -> None:
    assert [d.name for d in DM_TOOLS] == SPEC_TOOLS
    assert set(TOOL_EXECUTORS) == set(SPEC_TOOLS)


def test_tools_param_is_openai_shaped() -> None:
    params = dm_tools_param()
    assert len(params) == len(SPEC_TOOLS)
    for p in params:
        fn = p["function"]
        assert p["type"] == "function"
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert fn["parameters"].get("additionalProperties") is False
    subset = dm_tools_param(["no_mechanics"])
    assert [p["function"]["name"] for p in subset] == ["no_mechanics"]


def test_enums_in_schema() -> None:
    schema = dm_tools_param(["request_check"])[0]["function"]["parameters"]
    tiers = schema["$defs"]["DcTier"]["enum"]
    assert tiers == ["trivial", "easy", "medium", "hard", "very_hard", "nearly_impossible"]


def test_arg_bounds_reject_bad_shapes() -> None:
    with pytest.raises(ValidationError):
        tool_call("request_check", actor="fighter", ability_or_skill="luck", dc_tier="medium")
    with pytest.raises(ValidationError):
        tool_call("creative_effect", actor="fighter", effect_kind="meteor", severity="major")
    with pytest.raises(ValidationError):
        tool_call("creative_effect", actor="fighter", effect_kind="push", duration_rounds=11)
    with pytest.raises(ValidationError):
        IntroduceFeatureArgs.model_validate({"kind": "door", "name": "Seam", "hidden": True})
    with pytest.raises(ValidationError):
        GrantItemArgs.model_validate({"catalog_id": "gold", "qty": 10000})
    with pytest.raises(ValidationError):
        tool_call("start_encounter", terrain_tags=["forest"])
    with pytest.raises(ValidationError):
        tool_call("grant_xp", tier="legendary")
    with pytest.raises(ValidationError):
        tool_call("no_mechanics", gold=10000)


def test_execute_unknown_tool_and_wrong_args_model() -> None:
    state = party_state()
    rng = random.Random(1)
    unknown = execute_tool(
        state, ToolCall("c", "delete_world", NoMechanicsArgs()), ACTOR, rng, REGS
    )
    assert unknown.error is not None and unknown.events == ()
    wrong = execute_tool(state, ToolCall("c", "grant_xp", NoMechanicsArgs()), ACTOR, rng, REGS)
    assert wrong.error is not None and "invalid arguments" in wrong.error
    plain = execute_tool(state, ToolCall("c", "no_mechanics", NoMechanicsArgs()), ACTOR, rng, REGS)
    assert plain.ok and plain.events == ()
