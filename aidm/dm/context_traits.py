"""Foe traits for the fight context (M27.6, docs/next/GOAL_ITEMS.md "D: creative actions use the
same rules"): the AI must know a foe's weaknesses (a fire elemental's Water Susceptibility) to
let a player use them; the engine still owns every number.

One line per kind of foe in the fight (deduplicated by stat block, sorted by name): its SRD
special traits by name (`SrdMonster.special_abilities`), and for a trait that a row of
data/bg3/weaknesses.json grants, one short clause ("weak to water"). Spliced into the manifest by
THE context builder (`aidm.dm.context_sections.manifest_lines`) only while a fight is on. Token
budget: names only plus that clause, each line capped at `MAX_LINE_CHARS`.

Public API: `MAX_LINE_CHARS`, `foe_trait_lines(state, monster_ids) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.data.srd import srd
from aidm.data.weakness_defs import weaknesses_of
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState

MAX_LINE_CHARS = 160


def _trait_names(monster_index: str) -> list[str]:
    block = srd().monsters.find(monster_index)
    if block is None:
        return []
    weak = {e.trait: s for s, e in weaknesses_of(monster_index).items()}
    return [
        f"{a.name} (weak to {weak[a.name]})" if a.name in weak else a.name
        for a in block.special_abilities
    ]


def foe_trait_lines(state: GameState, monster_ids: Sequence[str]) -> list[str]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    kinds: dict[str, str] = {}
    for cid in monster_ids:
        index = state.creatures[cid].monster_index
        if index is not None and index not in kinds:
            block = srd().monsters.find(index)
            kinds[index] = block.name if block is not None else index
    lines: list[str] = []
    for index, name in sorted(kinds.items(), key=lambda kv: kv[1]):
        traits = _trait_names(index)
        if traits:
            line = f"Foe traits - {name}: {', '.join(traits)}"
            lines.append(
                line if len(line) <= MAX_LINE_CHARS else line[: MAX_LINE_CHARS - 3] + "..."
            )
    return lines
