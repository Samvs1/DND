"""The simulation's fake Dungeon Master (M27.10): the default FakeLLM answers, plus a search.

The fake model answers every adjudication with `no_mechanics`, so no exploration ever rolls.
The gear bots need one real check to see darkness at work: when the player's words contain
`SEARCH_TEXT`, this responder calls `request_check` (Perception, medium) for that hero, the way
a real model would; the engine adds the *Darkness* disadvantage in a dark unlit place. Every
other request gets `default_fake_step`.

Public API: `SEARCH_TEXT`, `sim_responder(hero_id_of)`.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from aidm.dm.context_text import PLAYER_TAG
from aidm.dm.fake_llm import FakeStep, default_fake_step, fake_tool_call
from aidm.dm.llm_backend import CompletionRequest

SEARCH_TEXT = "I search the dark corners for anything hidden"
_BLOCK = re.compile(rf'<{PLAYER_TAG} actor="([^"]*)">(.*?)</{PLAYER_TAG}>', re.DOTALL)


def _player_block(messages: Sequence[Mapping[str, Any]]) -> tuple[str, str] | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            found = _BLOCK.search(str(message.get("content", "")))
            return (found.group(1), found.group(2)) if found else None
    return None


def sim_responder(
    hero_id_of: Callable[[str], str | None],
) -> Callable[[CompletionRequest], FakeStep]:
    """`hero_id_of(name)` maps the acting hero's name (from the player block) to its id."""

    def respond(request: CompletionRequest) -> FakeStep:
        names = [t["function"]["name"] for t in request.tools or ()]
        answered = any(m.get("role") == "tool" for m in request.messages)
        offered = "request_check" in names and not answered  # one check, in the first round
        block = _player_block(request.messages) if offered else None
        if block is not None and SEARCH_TEXT.lower() in block[1].lower():
            hero = hero_id_of(block[0])
            if hero is not None:
                args = {"actor": hero, "ability_or_skill": "perception", "dc_tier": "medium"}
                return fake_tool_call("request_check", {**args, "reason": "search"})
        return default_fake_step(request)

    return respond
