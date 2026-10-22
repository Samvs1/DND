"""Reading a spell scroll (M27.7, docs/next/GOAL_ITEMS.md "Items": spell scrolls). PURE.

The item interpreter (`aidm.rules.item_effects`, effect `cast_spell`) calls `read_scroll`; it has
already spent the action (the use's `cost`) and consumes the scroll afterwards. Anyone may read
one (BG3): the spell goes through THE spell engine (`rules.spells.scroll_cast`) with no slot, at
the spell's own level, with the save DC and spell attack bonus of the SRD 5.1 Spell Scroll table
by spell level (data/bg3/item_uses.json `scroll_table`), never the reader's own numbers. A spell
line that adds "your spellcasting ability modifier" (Cure Wounds) uses the table's attack bonus
minus a +2 proficiency (docs/RULES_DECISIONS.md M27.7).

Aiming (one target: a creature id, a fight zone id or none): an area or point spell aimed at a
creature of the fight lands in that creature's zone; a self spell ignores the target; a creature
spell read at no one is read on the reader when it does not need a battlefield (Cure Wounds).
Outside a fight, a spell that needs a battlefield (`spell_targets.needs_battlefield`: an attack,
a save, damage, an area or a point):
- aimed at a creature or an NPC: refused, it is an attack; the fight starts first
  (`start_encounter` with the scroll id as `opening_attack`: a non-hostile NPC asks the player
  "Are you sure?" first, M15.1), then the opening strike reads it (`rules.opening_strike`);
- aimed at no one: it is read and spent with no special effect (owner rule 2026-10-22).
Any refusal of the spell engine (out of range, a bad target, no voice under Silence, a spell
that takes minutes during a fight) comes back as its message; nothing is spent.

Public API: `SCROLL_PROFICIENCY`, `scroll_numbers(level) -> CasterNumbers`,
`read_scroll(state, reader_id, item, spell_id, target, rng, regs) -> list[AnyEvent] | str`.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import item_use_data
from aidm.data.spell_defs import SpellDef
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.dice import Rng
from aidm.rules.scrolls import scroll_spell_index
from aidm.rules.spell_targets import CasterNumbers, needs_battlefield
from aidm.rules.spells import scroll_cast

SCROLL_PROFICIENCY = 2  # the table's +5 at levels 0-2 reads as +2 proficiency and +3 ability


def scroll_numbers(level: int) -> CasterNumbers:
    power = item_use_data().scroll_power(level)
    return CasterNumbers(
        save_dc=power.save_dc,
        attack_bonus=power.attack_bonus,
        modifier=power.attack_bonus - SCROLL_PROFICIENCY,
    )


def _fight(state: GameState, reader_id: str) -> Encounter | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return None
    return enc if reader_id in enc.combatants else None


def _aim(
    enc: Encounter | None, reader_id: str, spell: SpellDef, target: str | None
) -> tuple[Sequence[str], str | None]:
    kind = spell.targeting.kind
    if kind in ("area", "point"):
        there = enc.combatants.get(target or "") if enc is not None else None
        return (), there.zone_id if there is not None else target
    if kind == "self":
        return (), None
    if target is None:
        return ((), None) if needs_battlefield(spell) else ((reader_id,), None)
    return (target,), None


def _who(state: GameState, target: str | None) -> str | None:
    creature = state.creatures.get(target or "")
    if creature is not None:
        return creature.name
    npc = state.world.npcs.get(target or "")
    return npc.name if npc is not None else None


def _name(item: str) -> str:
    found = item_catalogue().find(item)
    return found.name if found is not None else item.replace("-", " ")


def read_scroll(
    state: GameState,
    reader_id: str,
    item: str,
    spell_id: str | None,
    target: str | None,
    rng: Rng,
    regs: CombatRegistries,
) -> list[AnyEvent] | str:
    index = spell_id or scroll_spell_index(item)
    spell = regs.spells.find(index) if index else None
    if spell is None:
        return f"The {_name(item)} holds no spell that works here; narrate it as flavour."
    enc = _fight(state, reader_id)
    if enc is None and needs_battlefield(spell):
        who = _who(state, target) if target != reader_id else None
        if who is None:
            return []  # read with no one to aim at: it happens, with no special effect
        return (
            f"Reading the {_name(item)} at {who} is an attack: start the fight first with"
            f" start_encounter (opening_strike_on that NPC, opening_attack {item!r});"
            " the engine reads the scroll as the opening strike."
        )
    try:
        numbers = scroll_numbers(spell.level)
        return scroll_cast(
            state, reader_id, spell, numbers, _aim(enc, reader_id, spell, target), rng, regs
        )
    except CommandRefused as error:
        return error.reason
