"""Names accepted as entity references (M4.8 live finding: DeepSeek passed "Aria", not an id)."""

import random
from pathlib import Path

from aidm.dm.adjudicator import AdjudicationOptions, adjudicate
from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.tool_refs import resolve_entity_ref, resolve_tool_refs
from aidm.dm.tools import RecordFactArgs, RequestSaveArgs
from aidm.models.events import AnyEvent, CheckResolved
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import add_dead, inn_state
from tests.ai.tool_fixtures import REGS


def test_resolve_ref_by_id_name_and_brackets() -> None:
    state = inn_state()
    assert resolve_entity_ref(state, "fighter", "creature") == "fighter"
    assert resolve_entity_ref(state, "Aria", "creature") == "fighter"
    assert resolve_entity_ref(state, " aria ", "creature") == "fighter"
    assert resolve_entity_ref(state, "[fighter]", "creature") == "fighter"
    assert resolve_entity_ref(state, "mira", "npc") == "npc-mira"
    assert resolve_entity_ref(state, "Captain Voss", "entity") == "npc-voss"
    assert resolve_entity_ref(state, "Sister Kelene", "creature") == "Sister Kelene"


def test_ambiguous_names_stay_unresolved() -> None:
    state = inn_state()
    add_dead(state, "gob-1", "Goblin", dead=False)
    add_dead(state, "gob-2", "Goblin", dead=False)
    assert resolve_entity_ref(state, "goblin", "creature") == "goblin"


def test_resolve_refs_copies_only_when_changed() -> None:
    state = inn_state()
    raw = {"actors": ["Aria", "rogue"], "ability": "dex", "dc_tier": "easy", "reason": "trap"}
    save = RequestSaveArgs.model_validate(raw)
    fixed = resolve_tool_refs(state, save)
    assert fixed.actors == ["fighter", "rogue"] and save.actors == ["Aria", "rogue"]
    fact = RecordFactArgs(text="Mira runs the inn.", entity_ids=["npc-mira"], tags=[])
    assert resolve_tool_refs(state, fact) is fact


async def test_live_finding_model_passes_names_not_ids(tmp_path: Path) -> None:
    state = inn_state()
    args = {"actor": "Aria", "ability_or_skill": "acrobatics", "dc_tier": "easy", "reason": "x"}
    client, _ = fake_client(tmp_path, [fake_tool_call("request_check", args)])
    applied: list[AnyEvent] = []

    def apply_fn(event: AnyEvent) -> None:
        applied.append(event)
        apply(state, event)

    result = await adjudicate(
        state,
        "fighter",
        "I climb onto the bar",
        client,
        AdjudicationOptions(),
        random.Random(1),
        REGS,
        apply_fn,
    )
    assert result.calls[0].result.ok
    checks = [e for e in applied if isinstance(e, CheckResolved)]
    assert checks and checks[0].creature_id == "fighter"
