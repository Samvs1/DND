"""Helpers for spell tests: casters with known spells and slots, and casting through commands."""

from __future__ import annotations

from collections.abc import Sequence

from aidm.models.abilities import Ability
from aidm.models.commands import CastCommand
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState, RechargeKind, Resource
from aidm.rules.spellcasting import SlotKind, slot_key
from tests.unit.rules.combat_fixtures import ScriptedRng, do
from tests.unit.rules.encounter_fixtures import make_pc

CASTING_ABILITY = {"wizard": Ability.INT, "cleric": Ability.WIS, "warlock": Ability.CHA}


def caster(
    cid: str,
    cls: str,
    *,
    cantrips: Sequence[str] = (),
    spells: Sequence[str] = (),
    level: int = 1,
    slots: dict[int, int] | None = None,
) -> Creature:
    """A PC of `cls` whose casting ability is 16 (+3) with the given spells ready."""
    pc_creature = make_pc(cid, class_index=cls)
    pc_creature.abilities[CASTING_ABILITY[cls]] = 16
    pc = pc_creature.pc
    assert pc is not None
    pc.level = level
    pc.cantrips = list(cantrips)
    if cls == "warlock":
        pc.spells_known = list(spells)
    else:
        pc.spellbook = list(spells) if cls == "wizard" else pc.spellbook
        pc.prepared = list(spells)
    for slot_level, count in (slots or {}).items():
        kind = SlotKind.PACT if cls == "warlock" else SlotKind.STANDARD
        pc_creature.resources[slot_key(kind, slot_level)] = Resource(
            current=count, maximum=count, recharge=RechargeKind.LONG_REST
        )
    return pc_creature


def cast(
    state: GameState,
    actor: str,
    spell: str,
    rng: ScriptedRng,
    *,
    targets: Sequence[str] = (),
    zone: str | None = None,
    slot: int | None = None,
) -> list[AnyEvent]:
    cmd = CastCommand(
        actor_id=actor, spell_id=spell, slot_level=slot, target_ids=tuple(targets), target_zone=zone
    )
    return do(state, cmd, rng)


def slots_left(creature: Creature, level: int) -> int:
    resource = creature.resources.get(slot_key(SlotKind.STANDARD, level))
    return 0 if resource is None else resource.current
