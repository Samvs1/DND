"""What the line hands over that the acting hero does not carry, and who does (M40.5). Pure.

Round 7 Z13 (r7b-typed 47-48): "Brienne hands Rook the blanket" changed nothing (Brienne
carries no blanket; Tamsin does) and the story told Rook refusing it, because the storyteller
was told only that nothing changed hands, not why. These are the engine's reasons, from the
heroes' packs and the registered names, never a phrase list:
- `held_elsewhere(state, actor_id, text)`: the things the line names (whole words, plurals
  too: `story_names.mentions`) that the acting hero carries none of while another hero does:
  catalogue gear by its plain name (`item_effects.gear_name`: "Blanket", "Torch") and keepsakes
  by their names, each with the heroes who carry it, in the order of the party.
- `named_heroes(state, actor_id, text)`: the other heroes the line names: their answers belong
  to their players, so the engine resolved none (nobody refused, declined or ignored it).

Public API: `HeldElsewhere`, `held_elsewhere(state, actor_id, text)`,
`named_heroes(state, actor_id, text)`.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_view import slug
from aidm.rules.story_names import mentions, text_slug


@dataclass(frozen=True)
class HeldElsewhere:
    name: str
    holders: tuple[str, ...]


def _heroes(state: GameState) -> list[Creature]:
    return sorted((c for c in state.creatures.values() if c.pc is not None), key=lambda c: c.id)


def _carried(hero: Creature) -> Iterator[str]:
    """The plain names of what a hero carries: gear and keepsakes."""
    if hero.pc is None:
        return
    for row in hero.pc.inventory:
        if row.qty > 0:
            yield gear_name(row.item)
    for keepsake in hero.pc.keepsakes:
        yield keepsake.name


def held_elsewhere(state: GameState, actor_id: str | None, text: str) -> tuple[HeldElsewhere, ...]:
    actor = state.creatures.get(actor_id or "")
    if actor is None or actor.pc is None or not text:
        return ()
    line = text_slug(text)
    own = {slug(name) for name in _carried(actor)}
    found: dict[str, tuple[str, list[str]]] = {}
    for hero in _heroes(state):
        if hero.id == actor.id:
            continue
        for name in _carried(hero):
            key = slug(name)
            if key in own or not mentions(line, key):
                continue
            holders = found.setdefault(key, (name, []))[1]
            if hero.name not in holders:
                holders.append(hero.name)
    return tuple(HeldElsewhere(name, tuple(holders)) for name, holders in found.values())


def named_heroes(state: GameState, actor_id: str | None, text: str) -> tuple[str, ...]:
    line = text_slug(text)
    return tuple(
        hero.name
        for hero in _heroes(state)
        if hero.id != actor_id and mentions(line, slug(hero.name))
    )
