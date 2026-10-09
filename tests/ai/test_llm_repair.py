"""M16.1: tool arguments with trailing data are accepted; rejected attempts log their errors."""

import json
from pathlib import Path

import pytest

from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.llm_log import MAX_ERROR_CHARS, MAX_LOG_ERRORS, short_errors
from aidm.dm.llm_types import ToolCallResult
from aidm.dm.llm_validate import parse_arguments
from tests.ai.fake_scripts import ECHO_TOOL, fake_client

GOOD = {"actor": "pc_1", "dc_tier": "medium"}
BAD = {"actor": "pc_1", "dc_tier": "impossible-ish"}


def test_parse_arguments_keeps_the_first_json_value() -> None:
    assert parse_arguments("") == {}
    assert parse_arguments("   \n") == {}
    assert parse_arguments('  {"a": 1}  ') == {"a": 1}
    assert parse_arguments('{"a": 1}\n{"b": 2}') == {"a": 1}
    assert parse_arguments('{"a": 1}}') == {"a": 1}
    with pytest.raises(json.JSONDecodeError):
        parse_arguments('{"a": 1')


async def test_trailing_extra_data_is_accepted_for_any_tool(tmp_path: Path) -> None:
    raw = json.dumps(GOOD) + " trailing words"
    client, fake = fake_client(tmp_path, [fake_tool_call("request_check", raw)])
    result = await client.call_tools([{"role": "user", "content": "x"}], [ECHO_TOOL])
    assert isinstance(result, ToolCallResult)
    assert result.attempts == 1 and len(fake.requests) == 1
    assert result.calls[0].args.model_dump() == GOOD


async def test_invalid_log_row_carries_errors_and_no_player_text(tmp_path: Path) -> None:
    secret_text = "I whisper the password swordfish to the guard"
    script = [fake_tool_call("request_check", BAD), fake_tool_call("request_check", GOOD)]
    client, _ = fake_client(tmp_path, script)
    messages = [{"role": "user", "content": secret_text}]
    await client.call_tools(messages, [ECHO_TOOL], player_text=secret_text)
    raw = (tmp_path / "llm.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [r["outcome"] for r in rows] == ["invalid", "ok"]
    assert rows[0]["errors"] and all("dc_tier" in e for e in rows[0]["errors"])
    assert "errors" not in rows[1]
    assert "swordfish" not in raw and "impossible-ish" not in raw
    assert "input_value" not in raw


def test_short_errors_cap_count_length_and_input_values() -> None:
    errors = [f"e{i}: bad, input_value='player words {i}', input_type=str" for i in range(9)]
    errors.append("x" * 500)
    short = short_errors(errors)
    assert len(short) == MAX_LOG_ERRORS
    assert short[0] == "e0: bad"
    assert all("player words" not in e for e in short)
    assert len(short_errors(["y" * 500])[0]) == MAX_ERROR_CHARS
