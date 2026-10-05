"""Helpers for spell tests: casters with known spells and slots, and casting through commands."""

from __future__ import annotations

from collections.abc import Sequence

from aidm.models.abilities import Ability
from aidm.models.commands import CastCommand, EndTurnCommand
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState, RechargeKind, Resource
from aidm.rules.spellcasting import SlotKind, slot_key
from aidm.rules.turns import begin_turn
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import ScriptedRng, do, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc

CASTING_ABILITY = {
    "wizard": Ability.INT,
    "cleric": Ability.WIS,
    "warlock": Ability.CHA,
    "ranger": Ability.WIS,
}


def caster(
    cid: str,
    cls: str,
    *,
    cantrips: Sequence[str] = (),
    spells: Sequence[str] = (),
    level: int = 1,
    slots: dict[int, int] | None = None,
) -> Creature:
    """A PC of `cls`: casting ability 16 (+3), the level's proficiency bonus, spells ready."""
    pc_creature = make_pc(cid, class_index=cls)
    pc_creature.abilities[CASTING_ABILITY[cls]] = 16
    pc = pc_creature.pc
    assert pc is not None
    pc.level = level
    pc_creature.proficiency_bonus = 2 + (level - 1) // 4
    pc.cantrips = list(cantrips)
    if cls in ("warlock", "ranger"):
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


def of[T](events: list[AnyEvent], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def battle(me: Creature, *others: tuple[str, str]) -> GameState:
    """`me` acts first in the gate; others are (id, zone): ids starting with g are monsters."""
    placements: list[tuple[Creature, Side, str]] = [(me, Side.PARTY, "gate")]
    for cid, zone in others:
        if cid.startswith("g"):
            placements.append((monster(cid, ac=13, hp=30), Side.HOSTILE, zone))
        else:
            placements.append((make_pc(cid), Side.PARTY, zone))
    return fight(placements)


def conditions_of(state: GameState, cid: str) -> list[str]:
    return [c.name for c in state.creatures[cid].conditions]


def next_turn(state: GameState, rng: ScriptedRng) -> list[AnyEvent]:
    """End the open turn, then open the next one; returns the events that opened it."""
    enc = state.encounter
    assert enc is not None
    active = enc.active_id()
    assert active is not None
    do(state, EndTurnCommand(actor_id=active), rng)
    events = begin_turn(rng, state)
    for event in events:
        apply(state, event)
    return events
