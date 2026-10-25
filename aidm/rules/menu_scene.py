"""Scene entries of the out-of-fight menu: people, looking, searching, travel, rest, shop (M36.3,
SPEC 6.2). Pure.

- `talk`: a word with a person standing here (the social path; a person who can teach answers
  from what they know);
- `look`, `inventory`, `what_now`: the plain answers (no roll, nothing spent);
- `search:perception`, `search:investigation`: a search of this place by watching and listening,
  or by going through things (one discovery check when something is hidden here);
- `travel`: every place the party knows (`menu_scene_view.places`): a place further on is walked
  hop by hop over the open roads, the place the party stands in is noted "you are here" (the
  engine answers it plainly, round 6 Y15), a locked way carries the world's reason
  (`rules.gateway_lock.locked_reason`, the engine's plain answer) and a place no open road
  reaches says so;
- `unlock`: picking, forcing or unlocking a locked way: the world's reason, never a roll (a
  progress gate is no lock, M29.7c R24);
- `rest:short`, `rest:long`: with their cost (short rests left, camp supplies); while a foe's
  offer waits here the note says the foe strikes first and no rest is taken (M35.2,
  `rules.waiting_foe`);
- `shop`: trading with a friendly shopkeeper standing here (`rules.shop.is_shop`).
While an encounter offer waits here (the `offer` scope) every travel destination but the place
itself notes that the offer is answered first (`move_party` never moves past a waiting offer;
Escape is the offer's way out); "you are here" stays plain. M36.8c: search and the shop stay on
the menu while foes wait (the engine runs the search check and the table shows the shop's
"trade with" button then too: never refuse the possible, the menu matches the buttons).

Public API: `scene_entries(view) -> list[MenuEntry]`, `info_entries()`.
"""

from aidm.models.abilities import Skill
from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.rules.menu_scene_view import SceneMenuView, places
from aidm.rules.rests import long_rest_cost, short_rests_left
from aidm.rules.shop import is_shop
from aidm.rules.social import npc_is_hostile

OFFER_FIRST_NOTE = "the waiting encounter is answered first (Escape slips away)"
FOE_STRIKES_NOTE = "a foe waits: it strikes first, no rest"
_SEARCHES = (
    (Skill.PERCEPTION, "Search this place by watching and listening (Perception)"),
    (Skill.INVESTIGATION, "Search this place by going through things (Investigation)"),
)


def info_entries() -> list[MenuEntry]:
    """The plain answers, open at any moment (in a fight too, on any turn)."""
    return [
        MenuEntry(
            id="inventory", kind=ActionKind.INVENTORY, label="Check what you carry", cost="free"
        ),
        MenuEntry(id="what_now", kind=ActionKind.WHAT_NOW, label="What now?", cost="free"),
    ]


def _talk(view: SceneMenuView) -> list[MenuEntry]:
    if not view.people:
        return []
    return [
        MenuEntry(
            id="talk",
            kind=ActionKind.TALK,
            label="Talk to someone here",
            target_ids=view.people,
            max_targets=1,
        )
    ]


def _searches() -> list[MenuEntry]:
    return [
        MenuEntry(
            id=f"search:{skill.value}", kind=ActionKind.SEARCH, label=label, skill=skill.value
        )
        for skill, label in _SEARCHES
    ]


def _travel(view: SceneMenuView) -> list[MenuEntry]:
    known = places(view)
    if not known:
        return []
    notes = {p.node_id: p.note for p in known if p.note}
    if view.offer is not None:  # the offer is answered first; "here" stays plain (Y15)
        notes |= {p.node_id: OFFER_FIRST_NOTE for p in known if not p.note}
    entries = [
        MenuEntry(
            id="travel",
            kind=ActionKind.TRAVEL,
            label="Travel to a place",
            target_ids=tuple(p.node_id for p in known),
            max_targets=1,
            target_notes=notes,
        )
    ]
    locked = [p for p in known if p.locked]
    if locked:
        entries.append(
            MenuEntry(
                id="unlock",
                kind=ActionKind.UNLOCK,
                label="Open a locked way (pick, force or unlock it)",
                target_ids=tuple(p.node_id for p in locked),
                max_targets=1,
                target_notes={p.node_id: p.note for p in locked},
            )
        )
    return entries


def _rests(view: SceneMenuView) -> list[MenuEntry]:
    state = view.state
    left = short_rests_left(state)
    cost, have = long_rest_cost(state), state.camp_supplies
    note = FOE_STRIKES_NOTE if view.threat else ""
    return [
        MenuEntry(
            id="rest:short",
            kind=ActionKind.REST,
            label=f"Short rest (1 hour, {left} left before a long rest)",
            option="short",
            note=note,
        ),
        MenuEntry(
            id="rest:long",
            kind=ActionKind.REST,
            label=f"Long rest (make camp: {cost} camp supplies, the party has {have})",
            option="long",
            note=note,
        ),
    ]


def _shop(view: SceneMenuView) -> list[MenuEntry]:
    world = view.state.world
    keepers = tuple(
        n
        for n in view.people
        if is_shop(view.state, world.npcs[n]) and not npc_is_hostile(world.npcs[n])
    )
    if not keepers:
        return []
    return [
        MenuEntry(
            id="shop",
            kind=ActionKind.SHOP,
            label="Trade with a shopkeeper here (see the wares)",
            target_ids=keepers,
            max_targets=1,
        )
    ]


def scene_entries(view: SceneMenuView) -> list[MenuEntry]:
    look = MenuEntry(id="look", kind=ActionKind.LOOK, label="Look around", cost="free")
    return [
        *_talk(view),
        look,
        *_searches(),
        *info_entries(),
        *_travel(view),
        *_rests(view),
        *_shop(view),
    ]
