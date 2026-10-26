"""Which registered things a story record's text names (M40.4). Pure.

A record names a thing when the thing's name, as a slug, appears in the record's text as whole
words (case and punctuation ignored; a plural "s" / "es" allowed): the closed world's own
names, never a phrase list. The names are the registry's (creatures with and without a
trailing counter, world NPCs, quests, world items, carried items and keepsakes) plus every name
the change ledger already holds (`World.changed`, "kind:name:<slug>"), so a foe removed after
its death is still recognised.

Public API: `text_slug(text) -> str`, `mentions(slugged, name_slug) -> bool`,
`registry_names(state) -> set[str]`, `named_slugs(state, text) -> set[str]` ("name:<slug>"
keys).
"""

import re

from aidm.models.state import GameState
from aidm.rules.story_keys import MIN_NAME, creature_names, story_name

_NAME = "name:"


def text_slug(text: str) -> str:
    return "-" + re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") + "-"


def mentions(slugged: str, name_slug: str) -> bool:
    """`slugged` comes from `text_slug`; `name_slug` is a bare slug ("old-sawmill")."""
    return len(name_slug) >= MIN_NAME and any(
        f"-{name_slug}{tail}-" in slugged for tail in ("", "s", "es")
    )


def registry_names(state: GameState) -> set[str]:
    world = state.world
    names: set[str] = set()
    for c in state.creatures.values():
        names.update(story_name(n) for n in creature_names(c.name))
        if c.pc is not None:
            names.update(story_name(i.item) for i in c.pc.inventory)
            names.update(story_name(k.name) for k in c.pc.keepsakes)
    names.update(story_name(n.name) for n in world.npcs.values())
    names.update(story_name(q.title) for q in world.quests.values())
    names.update(story_name(i.name) for i in world.items.values())
    return names


def _ledger_names(state: GameState) -> set[str]:
    out: set[str] = set()
    for key in state.world.changed:
        _, _, what = key.partition(":")
        if what.startswith(_NAME):
            out.add(what)
    return out


def named_slugs(state: GameState, text: str) -> set[str]:
    slugged = text_slug(text)
    names = registry_names(state) | _ledger_names(state)
    return {n for n in names if mentions(slugged, n.removeprefix(_NAME))}
