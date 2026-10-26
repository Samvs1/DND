"""Not-offered targets: names the line means that the menu cannot act on (M38.4, SPEC 6.2). Pure.

The M38.3 live eval found the most harmful false action: the line names a thing or a person the
menu does not offer for the act, and the model (or the validator's repair line "talk takes one
of: reeve-hallick") swaps in one that is offered: "I help Rook up" (Rook stands) helped the
downed Elowen up, "I ask my companions" talked to the tollman. The engine never acts on someone
the player did not name, so:
- `unoffered_targets(state, menu, text)`: the registered things the line spells out in full
  (whole words, case and punctuation ignored, the same game strings the exact fast path reads,
  never a phrase list) that the menu does not act on (no target shows the name, no entry names
  the thing): a keepsake another hero carries and the acting hero does not ("Sister's Locket
  (Rook carries it)") and an item lying at another place ("(not here)"); a name inside a shown
  one is that one. M38.5 fix: people who are not here are left out (a line about travelling to
  someone or asking about them named them as colour and drew a stray `other`). At most
  MAX_UNOFFERED, in the order the line names them. `with_unoffered(state, menu, text)` is the
  menu with them (`ActionMenu.unoffered`; no entry names one).
- `not_offered(menu, step)`: the step's NOT OFFERED targets: nothing can act on them, so the
  chooser turns that step into `other` with no repair round (`ChooseActionsArgs.to_choice`).
- `named_off(menu, step)`: M38.5 fix: the step's targets its entry cannot take that are a named
  being (a person, a hero, a foe, an id the menu does not list but a close misspelling) or, on
  an entry aimed at areas, an area it cannot reach (a move to where the hero stands). The
  validator rejects such a step with a repair line that names the entries that do take it
  (`takers`: the same item, "hand:crowbar" for "give:crowbar" to a hero) and says that a part
  no entry does is `other`, never another target. Places and things on the wrong entry, and
  creatures named for an area, keep the plain repair (the area holding it).
- `off_targets(menu, step)`: every target its entry cannot act on (zones aside); `menu_steps.
  step_acts` plays such a step as `OtherIntent` should one ever get past the validator.

Public API: `MAX_UNOFFERED`, `unoffered_targets(state, menu, text)`,
`with_unoffered(state, menu, text)`, `not_offered(menu, step)`, `named_off(menu, step)`,
`takers(menu, entry_id, target)`, `off_targets(menu, step)`.
"""

from collections.abc import Iterator
from difflib import get_close_matches

from aidm.models.action_menu import ActionMenu, MenuEntry, MenuStep, MenuTarget, TargetKind
from aidm.models.state import Creature, GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_view import slug

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


_BEINGS = frozenset({"person", "ally", "self", "foe"})


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry | None:
    return next((e for e in menu.entries if e.id == entry_id), None)


def _kinds(menu: ActionMenu) -> dict[str, TargetKind]:
    return {t.id: t.kind for t in (*menu.targets, *menu.unoffered)}


def not_offered(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    shown = {t.id for t in menu.unoffered}
    return tuple(t for t in step.targets if t in shown)


def off_targets(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    entry = _entry(menu, step.entry)
    if entry is None or entry.max_targets == 0:
        return ()
    kinds = _kinds(menu)
    areas = any(kinds.get(t) == "zone" for t in entry.target_ids)
    allowed = (*entry.target_ids, *entry.zone_ids)
    return tuple(
        target
        for target in step.targets
        if target not in allowed
        and (kinds.get(target) == "zone") is areas  # a creature for an area is repaired
        and (target in kinds or not get_close_matches(target, allowed, 1, _TYPO_CUTOFF))
    )


def named_off(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    kinds = _kinds(menu)
    shown = {t.id for t in menu.unoffered}
    return tuple(
        t
        for t in off_targets(menu, step)
        if t not in shown and (kinds.get(t) in _BEINGS or kinds.get(t) in (None, "zone"))
    )


def takers(menu: ActionMenu, entry_id: str, target: str) -> tuple[str, ...]:
    """The other entries for the same thing that take `target` ("hand:crowbar" for a
    "give:crowbar" aimed at a hero)."""
    tail = entry_id.split(":", 1)[1] if ":" in entry_id else None
    return tuple(
        e.id
        for e in menu.entries
        if tail is not None
        and e.id != entry_id
        and e.id.split(":", 1)[-1] == tail
        and target in e.target_ids
    )
