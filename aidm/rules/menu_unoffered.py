"""Not-offered targets: names the line means that the menu cannot act on (M38.4, SPEC 6.2). Pure.

The M38.3 live eval found the most harmful false action: the line names a thing or a person the
menu does not offer for the act, and the model (or the validator's repair) swaps in one that is
offered: "I help Rook up" (Rook stands) helped the downed Elowen up, "I ask my companions" talked
to the tollman, Rook's Sister's Locket became a carried item. The engine never acts on someone
the player did not name, so:
- `unoffered_targets(state, menu, text)`: the registered names the line spells out in full
  (whole words, case and punctuation ignored, the same game strings the exact fast path reads,
  never a phrase list) that the menu does not act on (no target shows the name, no entry names
  the thing): a keepsake another hero carries and the acting hero does not ("Sister's Locket
  (Rook carries it)"), an item lying at another place ("(not here)") and a person who is not
  here ("(not here)", "(dead)"); a name inside a shown one is that one ("the Saltwright" in
  "the Saltwright's forge", a place). At most
  MAX_UNOFFERED, in the order the line names them; only the ones the line names, so the prompt
  stays small. `with_unoffered(state, menu, text)` is the menu with them (`ActionMenu.unoffered`;
  no entry names one).
- `off_targets(menu, step)`: the step's targets its entry cannot act on: a not-offered target,
  an id the menu does not list (a close misspelling of an allowed id excepted), or a listed
  person, hero, foe, place or thing the entry does not list ("help_up" at a standing hero,
  "talk" at a waiting monster, "pay" to a hero). Such a step is the storyteller's (`other`),
  never a swapped target: the chooser's validator lets it through and `to_choice` turns it into
  `other`, and `menu_steps.step_acts` plays it as `OtherIntent` should one ever reach it. An
  entry aimed at areas (a move, an area spell) and an entry with no target keep the validator's
  repair: a creature named for an area is the area holding it, a target on "look" is a detail.

Public API: `MAX_UNOFFERED`, `unoffered_targets(state, menu, text)`,
`with_unoffered(state, menu, text)`, `off_targets(menu, step)`.
"""

from collections.abc import Iterator
from difflib import get_close_matches

from aidm.models.action_menu import ActionMenu, MenuStep, MenuTarget, TargetKind
from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_view import slug
from aidm.rules.scene import current_scene

MAX_UNOFFERED = 4
NOT_HERE = "not here"
_TYPO_CUTOFF = 0.85

type _Candidate = tuple[str, str, str, TargetKind]  # (id, name, where, kind)


def _keepsakes(hero: Creature) -> Iterator[tuple[str, str]]:
    """(id, name) of the keepsakes in a hero's pack (the registered things; catalogue gear is
    left out: its names are common words, "the Lantern Gate", "the bell-rope")."""
    for keepsake in hero.pc.keepsakes if hero.pc is not None else ():
        yield slug(keepsake.name) or slug(keepsake.id), keepsake.name


def _own(hero: Creature | None) -> set[str]:
    """The names of everything the acting hero carries (a thing they carry is no stand-in)."""
    if hero is None or hero.pc is None:
        return set()
    gear = {slug(gear_name(row.item)) for row in hero.pc.inventory if row.qty > 0}
    return gear | {slug(name) for _, name in _keepsakes(hero)}


def _carried_elsewhere(state: GameState, actor_id: str) -> Iterator[_Candidate]:
    own = _own(state.creatures.get(actor_id))
    for hero in sorted(state.creatures.values(), key=lambda c: c.id):
        if hero.pc is None or hero.id == actor_id:
            continue
        for thing, name in _keepsakes(hero):
            if slug(name) not in own:
                yield thing, name, f"{hero.name} carries it", "thing"


def _elsewhere(state: GameState) -> Iterator[_Candidate]:
    world = state.world
    here = set(current_scene(state).npc_ids)
    for npc in world.npcs.values():
        if npc.id not in here:
            yield npc.id, npc.name, "dead" if npc.dead else NOT_HERE, "person"
    for item in world.items.values():
        if not item.hidden and item.node_id not in (None, world.current_node):
            yield item.id, item.name, NOT_HERE, "thing"


def _shown(menu: ActionMenu) -> set[str]:
    """The names the menu already acts on: its targets' names ("Merre Wenslow", "Thug") and the
    things its entries name (`feed:potion-of-healing`, `take:free-given-salt`, `loot:<item>`)."""
    out: set[str] = set()
    for target in menu.targets:
        name = target.label.split(", ", 1)[0]
        out |= {slug(name), slug(name.split(" (", 1)[0]), slug(target.id)}
    for entry in menu.entries:
        out |= {entry.id.split(":", 1)[-1], entry.item or ""}
    return out - {""}


def _spans(line: str, keys: set[str]) -> list[tuple[int, int]]:
    """Where the line names a shown target (a name inside one, "the Saltwright" in "the
    Saltwright's forge", is that target, not another)."""
    out: list[tuple[int, int]] = []
    for key in keys:
        at = line.find(f"-{key}-")
        while at >= 0:
            out.append((at, at + len(key) + 2))
            at = line.find(f"-{key}-", at + 1)
    return out


def unoffered_targets(state: GameState, menu: ActionMenu, text: str) -> tuple[MenuTarget, ...]:
    line = f"-{slug(text)}-"
    shown = _shown(menu)
    spans = _spans(line, shown)
    taken = {t.id for t in menu.targets}
    found: list[tuple[int, MenuTarget]] = []
    for thing, name, where, kind in (
        *_carried_elsewhere(state, menu.actor_id),
        *_elsewhere(state),
    ):
        key = slug(name)
        at = line.find(f"-{key}-") if key else -1
        inside = any(a <= at and at + len(key) + 2 <= b for a, b in spans)
        if at < 0 or inside or key in shown or thing in taken:
            continue
        taken.add(thing)
        found.append((at, MenuTarget(id=thing, label=f"{name} ({where})", kind=kind)))
    found.sort(key=lambda pair: pair[0])
    return tuple(target for _, target in found[:MAX_UNOFFERED])


def with_unoffered(state: GameState, menu: ActionMenu, text: str) -> ActionMenu:
    unoffered = unoffered_targets(state, menu, text)
    return menu.model_copy(update={"unoffered": unoffered}) if unoffered else menu


def off_targets(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    entry = next((e for e in menu.entries if e.id == step.entry), None)
    if entry is None or entry.max_targets == 0:
        return ()
    kinds = {t.id: t.kind for t in (*menu.targets, *menu.unoffered)}
    if any(kinds.get(t) == "zone" for t in entry.target_ids):
        return ()  # an area aim: the validator repairs it (the area holding the creature)
    allowed = (*entry.target_ids, *entry.zone_ids)
    return tuple(
        target
        for target in step.targets
        if target not in allowed
        and kinds.get(target) != "zone"
        and (target in kinds or not get_close_matches(target, allowed, 1, _TYPO_CUTOFF))
    )
