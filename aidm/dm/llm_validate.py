"""Validation of raw tool calls against the tool arg models, and the retry feedback message.

Public API:
- `CallCheck(calls, errors, truncated)`: the outcome for one completion. `errors` are short,
  model-readable lines; `truncated` is True when the provider stopped on the token limit and the
  JSON did not parse (the client then raises `max_tokens` before retrying).
- `validate_tool_calls(completion, tools) -> CallCheck`: every call must name a listed tool and
  carry JSON object arguments that validate against its pydantic model (empty arguments = {}).
- `feedback_message(errors) -> dict`: the user-role message appended before a retry. It tells the
  model what was rejected and to answer again; it never echoes player text.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from aidm.dm.llm_backend import Completion, RawToolCall
from aidm.dm.llm_types import ToolCall, ToolDef

MAX_ERROR_LINES = 8


@dataclass(frozen=True)
class CallCheck:
    calls: tuple[ToolCall, ...] = ()
    errors: tuple[str, ...] = ()
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


def _pydantic_errors(name: str, exc: ValidationError) -> list[str]:
    out: list[str] = []
    for err in exc.errors()[:4]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(arguments)"
        out.append(f"{name}: {loc}: {err.get('msg', 'invalid')}")
    return out


def _check_one(raw: RawToolCall, tools: Mapping[str, ToolDef]) -> tuple[ToolCall | None, list[str]]:
    defn = tools.get(raw.name)
    if defn is None:
        listed = ", ".join(sorted(tools))
        return None, [f"unknown tool {raw.name!r}; use only: {listed}"]
    try:
        data: Any = json.loads(raw.arguments) if raw.arguments.strip() else {}
    except json.JSONDecodeError as exc:
        return None, [f"{raw.name}: arguments are not valid JSON ({exc.msg} at char {exc.pos})"]
    if not isinstance(data, dict):
        return None, [f"{raw.name}: arguments must be a JSON object"]
    try:
        args = defn.args_model.model_validate(data)
    except ValidationError as exc:
        return None, _pydantic_errors(raw.name, exc)
    return ToolCall(id=raw.id, name=raw.name, args=args), []


def validate_tool_calls(completion: Completion, tools: Mapping[str, ToolDef]) -> CallCheck:
    calls: list[ToolCall] = []
    errors: list[str] = []
    bad_json = False
    for raw in completion.tool_calls:
        call, errs = _check_one(raw, tools)
        if call is not None:
            calls.append(call)
        errors.extend(errs)
        bad_json = bad_json or any("not valid JSON" in e for e in errs)
    truncated = completion.finish_reason == "length" and (bad_json or not completion.tool_calls)
    if truncated and not errors:
        errors.append("the answer was cut off by the token limit")
    return CallCheck(tuple(calls), tuple(errors[:MAX_ERROR_LINES]), truncated)


def feedback_message(errors: tuple[str, ...], *, truncated: bool = False) -> dict[str, Any]:
    lines = "\n".join(f"- {e}" for e in errors)
    hint = " Keep arguments short." if truncated else ""
    return {
        "role": "user",
        "content": (
            "ENGINE VALIDATOR: your previous tool calls were rejected and nothing was executed:\n"
            f"{lines}\nCall the tools again with corrected arguments, using only the listed "
            f"tools, fields and enum values.{hint}"
        ),
    }
