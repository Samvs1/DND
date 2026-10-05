"""Client-facing types of the LLM layer (SPEC 4 DeepSeek, 6.1).

Public API:
- `LlmRole`: FAST (routing, extraction, summaries) / QUALITY (narration, social, NPC voice).
- `LlmMode`: LIVE (DeepSeek), FAKE (`AIDM_FAKE_LLM=1`, deterministic), DISABLED (no key: every
  call returns an `LlmFailure` so callers use their template fallbacks; the host sees a banner).
- `ToolDef(name, description, args_model)`: one callable tool; `tool_param(defn)` exports it as
  an OpenAI `tools` entry (JSON schema from the pydantic model).
- `ToolCall(id, name, args)`: one VALIDATED tool call (`args` is an instance of the tool's model).
- `ToolCallResult(calls, content, attempts)`: the validated answer of `LlmClient.call_tools`.
- `FailureReason` / `LlmFailure(reason, detail, attempts)`: the typed failure every client method
  returns instead of raising (timeout, transport error, validation exhausted, disabled).
- `TokenTotals`: running counters per role (calls, failures, prompt and completion tokens) for
  the host panel.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class LlmRole(StrEnum):
    FAST = "fast"
    QUALITY = "quality"


class LlmMode(StrEnum):
    LIVE = "live"
    FAKE = "fake"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    args_model: type[BaseModel]


def tool_param(defn: ToolDef) -> dict[str, Any]:
    """The OpenAI-compatible `tools` entry for one tool (the engine validates again anyway)."""
    schema = defn.args_model.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {"name": defn.name, "description": defn.description, "parameters": schema},
    }


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: BaseModel


@dataclass(frozen=True)
class ToolCallResult:
    calls: tuple[ToolCall, ...] = ()
    content: str = ""
    attempts: int = 1


class FailureReason(StrEnum):
    DISABLED = "disabled"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    VALIDATION = "validation"
    EMPTY = "empty"


@dataclass(frozen=True)
class LlmFailure:
    reason: FailureReason
    detail: str = ""
    attempts: int = 0


@dataclass
class RoleTotals:
    calls: int = 0
    failures: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class TokenTotals:
    by_role: dict[LlmRole, RoleTotals] = field(
        default_factory=lambda: {role: RoleTotals() for role in LlmRole}
    )

    def add(self, role: LlmRole, prompt: int, completion: int, *, failed: bool) -> None:
        row = self.by_role[role]
        row.calls += 1
        row.failures += int(failed)
        row.prompt_tokens += prompt
        row.completion_tokens += completion

    @property
    def total_tokens(self) -> int:
        return sum(r.prompt_tokens + r.completion_tokens for r in self.by_role.values())

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {
            role.value: {
                "calls": r.calls,
                "failures": r.failures,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
            }
            for role, r in self.by_role.items()
        }
