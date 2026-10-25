"""Every hotbar action the sheet offers appears in the fight menu (M36.2, SPEC 6.2).

Walks committed playtest fixtures (casters, items, the round-6 runs) through the one reducer and,
at each typed line on a hero's own open turn, checks the menu against the hotbar's sources: every
attack line, castable spell, feature action with uses left, consumable, gear use, condition that
an action can end and standard action. An entry may only be missing when the real command
refuses every candidate target (checked here with the same probe the hotbar's server uses).
"""

from collections.abc import Callable, Iterator, Sequence

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import ActionMenu
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    FeatureActionCommand,
    RefusalCode,
    UseItemCommand,
)
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EconomyChanged, TurnStarted
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_probe import ready_state, refusal
from aidm.rules.menu_view import FightView, fight_view
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, replay_until

REGS = combat_registries()
RUNS = ("r3-casters", "r3-items", "m31-r4-full", "m32-r5-full", "m35-r6-typed", "m35-r6-full")
PER_RUN = 12
_REACH = (None, RefusalCode.OUT_OF_RANGE)
type Aims = Callable[[tuple[str, ...], str | None], AnyCommand]


def _hero_acting(state: GameState) -> str | None:
    """The hero whose turn is open in an active fight, if any."""
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE or not enc.turn_open:
        return None
    actor = enc.active_id()
    creature = state.creatures.get(actor or "")
    return actor if creature is not None and creature.pc is not None else None


def _hero_turns(run: str) -> Iterator[tuple[GameState, str]]:
    """The state before a hero's first spend of a turn or before a typed line on it."""
    log = events_of(run)
    state = replay_until(run, log[0].seq)
    found, fresh = 0, False
    for entry in log:
        event = entry.event
        actor = _hero_acting(state)
        moment = isinstance(event, ActionDeclared) or (fresh and isinstance(event, EconomyChanged))
        if actor is not None and moment and found < PER_RUN:
            found += 1
            fresh = False
            yield state, actor
        apply(state, event)
        fresh = fresh or isinstance(event, TurnStarted)


def _any(view: FightView, commands: Sequence[AnyCommand], ok: tuple[object, ...]) -> bool:
    ready = ready_state(view.state, view.actor_id)
    return any(refusal(ready, c, REGS) in ok for c in commands)


def _aims(view: FightView, build: Aims) -> list[AnyCommand]:
    creatures = (*view.foes, *view.allies, view.actor_id)
    zones = [z.id for z in view.encounter.zone_map.zones]
    return [
        build((), None),
        *(build((c,), None) for c in creatures),
        *(build((), z) for z in zones),
    ]


def _attack_gaps(view: FightView, menu: ActionMenu) -> list[str]:
    gaps: list[str] = []
    for line in view.sheet.attacks:
        tries = [
            AttackCommand(actor_id=view.actor_id, target_id=f, option=line.hand) for f in view.foes
        ]
        if not any(e.option == line.hand for e in menu.entries) and _any(view, tries, _REACH):
            gaps.append(f"attack {line.hand}")
    return gaps


def _magic_gaps(view: FightView, menu: ActionMenu) -> list[str]:
    gaps: list[str] = []
    block = view.sheet.spellcasting
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)] if block else []
    for spell in (s for s in lines if s.prepared):

        def cast(ids: tuple[str, ...], zone: str | None, index: str = spell.index) -> AnyCommand:
            return CastCommand(
                actor_id=view.actor_id, spell_id=index, target_ids=ids, target_zone=zone
            )

        if not any(e.spell_id == spell.index for e in menu.entries) and _any(
            view, _aims(view, cast), (None,)
        ):
            gaps.append(f"cast {spell.index}")
    for feat in (f for f in view.sheet.feature_actions if f.available):

        def use(ids: tuple[str, ...], zone: str | None, index: str = feat.feature) -> AnyCommand:
            return FeatureActionCommand(
                actor_id=view.actor_id, feature_id=index, target_ids=ids, target_zone=zone
            )

        aimed = feat.target_kind in ("creature", "creatures") or feat.range_kind != "self"
        needed = not aimed or _any(view, _aims(view, use), (None,))
        if needed and not any(e.feature_id == feat.feature for e in menu.entries):
            gaps.append(f"feature {feat.feature}")
    return gaps


def _item_gaps(view: FightView, menu: ActionMenu) -> list[str]:
    gaps: list[str] = []
    for use in view.sheet.gear_uses:

        def gear(
            ids: tuple[str, ...], zone: str | None, u: str = use.use_id, i: str = use.item
        ) -> AnyCommand:
            target = ids[0] if ids else None
            return UseItemCommand(
                actor_id=view.actor_id, item=i, use_id=u, target_id=target, target_zone=zone
            )

        needed = use.target == "none" or _any(view, _aims(view, gear), (None,))
        if needed and not any(e.use_id == use.use_id for e in menu.entries):
            gaps.append(f"gear {use.use_id}")
    for row in view.sheet.inventory:
        if REGS.consumables.find(row.item) is None:
            continue
        tries = [
            UseItemCommand(actor_id=view.actor_id, item=row.item, target_id=c)
            for c in (view.actor_id, *view.allies)
        ]
        if _any(view, tries, (None,)) and not any(e.id == f"item:{row.item}" for e in menu.entries):
            gaps.append(f"item {row.item}")
    return gaps


def _standard_gaps(view: FightView, menu: ActionMenu) -> list[str]:
    ids = {e.id for e in menu.entries}
    wanted = {"move", "dash", "disengage", "dodge", "hide", "flee", "end-turn"}
    if view.foes:
        wanted |= {"throw", "shove:prone", "shove:push"}
    if view.allies:
        wanted.add("help")
    wanted |= {f"end:{c.name}" for c in view.sheet.conditions if c.end_label}
    if any(f.index == "cunning-action" for f in view.sheet.features):
        wanted |= {"dash:bonus", "disengage:bonus", "hide:bonus"}
    return sorted(wanted - ids)


def test_every_hotbar_action_is_on_the_fight_menu() -> None:
    checked = 0
    for run in RUNS:
        for state, actor in _hero_turns(run):
            menu = build_menu(state, actor, REGS)
            view = fight_view(state, actor, REGS)
            gaps = [
                *_attack_gaps(view, menu),
                *_magic_gaps(view, menu),
                *_item_gaps(view, menu),
                *_standard_gaps(view, menu),
            ]
            assert gaps == [], f"{run} {actor}: {gaps}"
            checked += 1
    assert checked >= 40
