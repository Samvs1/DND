"""Shared states for the item-use tests (M27.3): the sample campaign, heroes carrying gear."""

from __future__ import annotations

import functools
import random
from collections.abc import Sequence

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.character import InventoryItem, Keepsake
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent
from aidm.models.item_events import ItemUseRefused
from aidm.models.state import Creature, GameState
from aidm.models.world_events import PartyMoved
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.campaign_install import install_campaign
from aidm.rules.item_use import use_item
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import ScriptedRng, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc

CAVE = "saltcellar-tunnels"  # cave, crypt: dark
DOCKS = "gullmere-quay-docks"  # village, bridge: not dark, water for fishing
SHRINE = "thornwood-shrine"  # forest, wilds: hunting ground

type Gear = str | tuple[str, int]


@functools.cache
def _install() -> tuple[AnyEvent, ...]:
    return tuple(install_campaign(GameState(campaign_id="gear", seed=1), load_sample_campaign(), 1))


def hero(
    cid: str = "hero",
    gear: Sequence[Gear] = (),
    *,
    keepsakes: Sequence[str] = (),
    tools: Sequence[str] = (),
) -> Creature:
    """A human fighter carrying `gear` (id or (id, qty)), keepsakes by name, tool proficiencies."""
    creature = make_pc(cid)
    pc = creature.pc
    assert pc is not None
    pc.inventory = [
        InventoryItem(item=g, qty=1) if isinstance(g, str) else InventoryItem(item=g[0], qty=g[1])
        for g in gear
    ]
    pc.keepsakes = [Keepsake(id=f"k-{i}", name=name) for i, name in enumerate(keepsakes)]
    pc.tool_proficiencies = list(tools)
    return creature


def at(node: str, *heroes: Creature) -> GameState:
    state = GameState(campaign_id="gear", seed=1)
    for event in _install():
        apply(state, event)
    apply(state, PartyMoved(from_node=state.world.current_node, to_node=node, scene_index=1))
    for creature in heroes:
        state.creatures[creature.id] = creature
    return state


def chain() -> ZoneMap:
    """Three zones in a row, 15 ft hops: a - b - c."""
    zones = [Zone(id=z, name=z.upper()) for z in "abc"]
    return ZoneMap(
        zones=zones, edges=[ZoneEdge(a="a", b="b", feet=15), ZoneEdge(a="b", b="c", feet=15)]
    )


def gear_fight(node: str, me: Creature, *others: tuple[Creature, Side, str]) -> GameState:
    """A fight at `node` on the a-b-c chain; `me` stands in a and acts first."""
    placements = [(me, Side.PARTY, "a"), *others]
    if not others:
        placements.append((monster("gob"), Side.HOSTILE, "c"))
    return fight(placements, chain(), base=at(node))


def use(
    state: GameState,
    item: str,
    target: str | None = None,
    *,
    actor: str = "hero",
    rng: random.Random | ScriptedRng | None = None,
    resting: bool = False,
    prior: Sequence[AnyEvent] = (),
) -> list[AnyEvent]:
    return use_item(
        state,
        actor,
        item,
        target,
        rng=rng or random.Random(7),
        resting=resting,
        prior=prior,
    )


def run(state: GameState, events: Sequence[AnyEvent]) -> None:
    for event in events:
        apply(state, event)


def refusal(events: Sequence[AnyEvent]) -> str:
    """The message of a refused use: the ONLY event is `ItemUseRefused`."""
    assert len(events) == 1, events
    event = events[0]
    assert isinstance(event, ItemUseRefused), event
    return event.message


def qty(state: GameState, cid: str, item: str) -> int:
    pc = state.creatures[cid].pc
    assert pc is not None
    return next((e.qty for e in pc.inventory if e.item == item), 0)
