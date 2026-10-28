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
  menu with them (`ActionMenu.unoffered`; no entry names one). M40.2 (round 7 Z2: "We follow
  Sersha's trail to the Gear Nave", a locked tier-3 place, travelled to a place the menu did
  offer): out of a fight, a place the party has heard of from its journal (the quests it holds
  and its leads name it) or a map use (`World.charted`; the visited places and their roads are
  travel targets already) that no road open now reaches, with the engine's reason
  (`gateway_lock.short_reason`: "locked until the master of X is dealt with", or
  `NO_ROAD_NOTE`). A place the party never heard of is never one. M41.2 (round 7 Z5: "Tamsin
  sends a guiding bolt at the armor" with no slot left cast Sacred Flame): a ready spell of the
  hero's that no entry offers because the hero cannot pay for it (`ActionMenu.unready`, from
  `rules.spell_ready`, labelled with the reason: "Tamsin has no 1st-level slot left").
- M41.3 (round 7 Z7): `with_unoffered` also keeps, of the heroes who may do a shared step
  (`ActionMenu.helpers`), only the ones the line names (`named_helpers`: the hero's name or its
  first word, whole words), so a line that names no other hero is read as before.
- `not_offered(menu, step)`: the step's NOT OFFERED targets: nothing can act on them, so the
  validator never repairs that step (M43.2: the engine refuses it with the reason, `refusal`).
  M41.2: an entry id the menu does not hold whose last part is a NOT OFFERED id
  (`cast:guiding-bolt`) names it too, so it is never repaired into a listed stand-in.
- `named_off(menu, step)`: M38.5 fix: the step's targets its entry cannot take that are a named
  being (a person, a hero, a foe, an id the menu does not list but a close misspelling) or, on
  an entry aimed at areas, an area it cannot reach (a move to where the hero stands). The
  validator rejects such a step with a repair line that names the entries that do take it
  (`takers`: the same item, "hand:crowbar" for "give:crowbar" to a hero) and says that a part
  no entry does is `other`, never another target. Places and things on the wrong entry, and
  creatures named for an area, keep the plain repair (the area holding it), except a fight cast
  or feature, which `engine_answers` sends as named.
- `off_targets(menu, step)`: every target its entry cannot act on (zones aside); `menu_steps.
  step_acts` refuses such a step should one ever get past the validator (M43.2).
- `engine_answers(menu, step)`: the validator passes the step as it is (refused with its
  reason, or a fight spell or feature the real command answers).
- `refusal(menu, step)`, `other_refusal(menu, text)`: the reason a NOT OFFERED thing carries.
- `as_entry(menu, text)`: in a fight, an `other` part naming one weapon, spell or feature entry
  and what it aims at is that entry.
- `named_creatures(menu, text)`: M44.2: the creatures the line names, in its order, the hero
  aside (`menu_aim.line_aim`).
- `GOLD_SUM`: a sum of gold a line names (one over the hero's purse is NOT OFFERED);
  `gold_refusal(menu)` its reason (M44.3).

Public API: `MAX_UNOFFERED`, `unoffered_targets(state, menu, text)`,
`with_unoffered(state, menu, text)`, `named_helpers(state, menu, text)`, `not_offered(menu,
step)`, `named_off(menu, step)`, `engine_answers(menu, step)`, `refusal(menu, step)`,
`other_refusal(menu, text)`, `as_entry(menu, text)`, `named_creatures(menu, text)`,
`takers(menu, entry_id, target)`, `off_targets(menu, step)`, `GOLD_SUM`, `gold_refusal(menu)`.
"""

import re
from collections.abc import Iterator
from difflib import get_close_matches

from aidm.models.action_menu import (
    ActionKind,
    ActionMenu,
    MenuEntry,
    MenuScope,
    MenuStep,
    MenuTarget,
    TargetKind,
)
from aidm.models.state import Creature, GameState
from aidm.rules.gateway_lock import short_reason
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_scene_view import NO_ROAD_NOTE
from aidm.rules.menu_view import slug
from aidm.rules.story_names import mentions, text_slug
from aidm.rules.world_graph import travel_route

MAX_UNOFFERED = 4
NOT_HERE = "not here"
_TYPO_CUTOFF = 0.85
GOLD_SUM = re.compile(r"\b(\d+)\s*(?:gold|gp)\b")
GOLD_ID = "gold-"
_AIMED_MAGIC = frozenset({ActionKind.CAST, ActionKind.FEATURE})

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


def _journal(state: GameState) -> str:
    """The journal's words as one slug: the quests the party holds and its leads."""
    world = state.world
    texts = [" ".join((q.title, q.objective, *q.log)) for q in world.quests.values()]
    return f"-{slug(' '.join([*texts, *(lead.text for lead in world.leads)]))}-"


def _out_of_reach(state: GameState, menu: ActionMenu) -> Iterator[_Candidate]:
    """M40.2: the places the journal names or a map charted that no road open now reaches (the
    places a travel entry takes are targets already, and `unoffered_targets` skips them)."""
    world = state.world
    if menu.scope not in (MenuScope.EXPLORE, MenuScope.OFFER) or world.current_node is None:
        return
    told = _journal(state)
    for node, name in world.node_names.items():
        key = slug(name)
        heard = node in world.charted or f"-{key}-" in told
        if not key or not heard or node == world.current_node:
            continue
        if travel_route(world, world.current_node, node):
            continue
        where = short_reason(state, node) if node in world.locked_nodes else NO_ROAD_NOTE
        yield node, name, where, "place"


def _unready(menu: ActionMenu) -> Iterator[_Candidate]:
    """M41.2: the hero's ready spells it cannot pay for, with the reason."""
    for target in menu.unready:
        name, _, reason = target.label.partition(" (")
        yield target.id, name, reason.removesuffix(")"), target.kind


def _gold_over(state: GameState, actor_id: str, text: str) -> Iterator[_Candidate]:
    """M43.2 (round 8 AA6): a sum of gold the line names that the hero does not have."""
    hero = state.creatures.get(actor_id)
    if hero is None or hero.pc is None:
        return
    for found in GOLD_SUM.finditer(text.lower()):
        amount = int(found.group(1))
        if amount > hero.pc.gold:
            where = f"{hero.name} has only {hero.pc.gold} gold"
            yield f"{GOLD_ID}{amount}", found.group(0), where, "thing"


def _shown(menu: ActionMenu) -> set[str]:
    """The names the menu already acts on: its targets' names ("Merre Wenslow", "Thug") and the
    things its entries name (`feed:potion-of-healing`, `take:free-given-salt`, `loot:<item>`).
    M44.2 (round 9 BB4): a spent out-of-fight cast of a spell the hero cannot pay for names it
    for the rules' plain answer only, so a line naming that spell still has it NOT OFFERED."""
    out: set[str] = set()
    unpaid = {t.id for t in menu.unready}
    for target in menu.targets:
        name = target.label.split(", ", 1)[0]
        out |= {slug(name), slug(name.split(" (", 1)[0]), slug(target.id)}
    for entry in menu.entries:
        if entry.spent and entry.spell_id in unpaid:
            continue
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
        *_out_of_reach(state, menu),
        *_unready(menu),
        *_gold_over(state, menu.actor_id, text),
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


def named_helpers(state: GameState, menu: ActionMenu, text: str) -> tuple[str, ...]:
    """M41.3: the helpers the line names (their name, or its first word, as whole words)."""
    line = text_slug(text)
    out: list[str] = []
    for hero_id in menu.helpers:
        hero = state.creatures.get(hero_id)
        name = hero.name.strip() if hero is not None else ""
        forms = {slug(name), slug(name.split(" ", 1)[0])} - {""}
        if any(mentions(line, form) for form in forms):
            out.append(hero_id)
    return tuple(out)


def with_unoffered(state: GameState, menu: ActionMenu, text: str) -> ActionMenu:
    unoffered = unoffered_targets(state, menu, text)
    helpers = named_helpers(state, menu, text)
    if not unoffered and helpers == menu.helpers:
        return menu
    return menu.model_copy(update={"unoffered": unoffered, "helpers": helpers})


_BEINGS = frozenset({"person", "ally", "self", "foe"})


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry | None:
    return next((e for e in menu.entries if e.id == entry_id), None)


def _kinds(menu: ActionMenu) -> dict[str, TargetKind]:
    return {t.id: t.kind for t in (*menu.targets, *menu.unoffered)}


def not_offered(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    shown = {t.id for t in menu.unoffered}
    named = tuple(t for t in step.targets if t in shown)
    tail = step.entry.split(":", 1)[-1]
    if tail in shown and tail not in named and _entry(menu, step.entry) is None:
        return (tail, *named)
    return named


def _unlisted(menu: ActionMenu, entry: MenuEntry, step: MenuStep) -> tuple[str, ...]:
    """The step's targets its entry does not list (a close misspelling of a listed one aside)."""
    allowed = (*entry.target_ids, *entry.zone_ids)
    kinds = _kinds(menu)
    return tuple(
        t
        for t in step.targets
        if t not in allowed and (t in kinds or not get_close_matches(t, allowed, 1, _TYPO_CUTOFF))
    )


def off_targets(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    entry = _entry(menu, step.entry)
    if entry is None or entry.max_targets == 0:
        return ()
    kinds = _kinds(menu)
    areas = any(kinds.get(t) == "zone" for t in entry.target_ids)
    # a creature named for an area is the validator's plain repair (the area holding it); a
    # fight cast or feature goes as named (`engine_answers`, `menu_steps._area_aim`)
    return tuple(t for t in _unlisted(menu, entry, step) if (kinds.get(t) == "zone") is areas)


def named_off(menu: ActionMenu, step: MenuStep) -> tuple[str, ...]:
    kinds = _kinds(menu)
    shown = {t.id for t in menu.unoffered}
    return tuple(
        t
        for t in off_targets(menu, step)
        if t not in shown and (kinds.get(t) in _BEINGS or kinds.get(t) in (None, "zone"))
    )


def engine_answers(menu: ActionMenu, step: MenuStep) -> bool:
    """M43.2: the validator passes this step as it is: it names a NOT OFFERED thing (refused
    with its reason), or it is a spell or feature aimed at a target its entry does not list
    (the real command says why not)."""
    if not_offered(menu, step):
        return True
    entry = _entry(menu, step.entry)
    if menu.scope is not MenuScope.FIGHT or entry is None or entry.kind not in _AIMED_MAGIC:
        return False
    return bool(_unlisted(menu, entry, step))


def _reason(target: MenuTarget) -> str:
    """Every NOT OFFERED label is "<name> (<why>)" (`unoffered_targets`)."""
    name, _, where = target.label.partition(" (")
    return f"{name}: {where.removesuffix(')')}."


def refusal(menu: ActionMenu, step: MenuStep) -> str | None:
    """M43.2: why a step at a NOT OFFERED thing cannot be done, from that thing's label."""
    named = not_offered(menu, step)
    return next(_reason(t) for t in menu.unoffered if t.id == named[0]) if named else None


def other_refusal(menu: ActionMenu, text: str) -> str | None:
    """M43.2: an `other` part that names a NOT OFFERED thing is refused with its reason."""
    line = text_slug(text)
    for target in menu.unoffered:
        if mentions(line, slug(target.label.partition(" (")[0])):
            return _reason(target)
    return None


def gold_refusal(menu: ActionMenu) -> str | None:
    """M44.3 (BB12): the reason of a sum of gold the line names that is over the hero's purse."""
    return next((_reason(t) for t in menu.unoffered if t.id.startswith(GOLD_ID)), None)


_NAMED_KINDS = frozenset({ActionKind.ATTACK, ActionKind.CAST, ActionKind.FEATURE, ActionKind.THROW})


def _target_name(target: MenuTarget) -> str:
    return target.label.split(", ", 1)[0].split(" (", 1)[0]


_CREATURES = frozenset({"foe", "ally", "person"})


def named_creatures(menu: ActionMenu, text: str) -> tuple[str, ...]:
    """M44.2: the creatures of the menu (the hero aside) the line names, in the line's order."""
    line = text_slug(text)
    keys = {t.id: slug(_target_name(t)) for t in menu.targets if t.kind in _CREATURES}
    named = [cid for cid, key in keys.items() if mentions(line, key)]
    return tuple(sorted(named, key=lambda cid: line.find(f"-{keys[cid]}")))


def as_entry(menu: ActionMenu, text: str) -> MenuStep | None:
    """M43.2 (B2; round 8 AA4, round 5 X1): in a fight, an `other` part that names the thing of
    exactly one weapon, spell or feature entry (its id's last part: `cast:thunderwave`) and a
    creature or area of the fight (not the hero) is that entry aimed at what it names."""
    if menu.scope is not MenuScope.FIGHT:
        return None
    line = text_slug(text)
    hits = [
        e for e in menu.entries if e.kind in _NAMED_KINDS and mentions(line, e.id.split(":", 1)[-1])
    ]
    aimed = tuple(
        t.id for t in menu.targets if t.kind != "self" and mentions(line, slug(_target_name(t)))
    )
    if len(hits) != 1 or not aimed:
        return None
    return MenuStep(entry=hits[0].id, targets=aimed[: max(1, hits[0].max_targets)])


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
