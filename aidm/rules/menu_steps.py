"""THE step executor's pure half: a validated menu choice as the acts the session runners take
(M36.4, SPEC 6.2, docs/next/M36_ACTION_MENU.md). Pure: plans, never applies.

`to_acts(state, menu, choice, regs, text="")` turns the model's pick into the exact act and
command objects the button paths already run (`session.intent_turn.run_intent`,
`session.fight_text`, `combat_flow.player_command`, the client handlers), in the order chosen.
Engine meaning lives here and in `menu_steps_fight` / `menu_steps_scene`, never in wording.
- `other` is one `OtherIntent(actor, text)`: the storyteller's creative or social call, with
  the off-menu part's words (`choice.other_text`, else the whole line). With steps too (M36.5)
  it comes before them when `other_first`, else after them unless a step ended the line.
- A strike with `starts_fight` (the offer scope) is `OfferStrikeIntent(actor, step)` and ends the
  steps: the offer is answered as Fight and the step itself waits for the hero's turn, when
  `resume_strike` maps it onto the spawned creatures (below). M36.8c: a weapon strike out of a
  fight aimed at a person here (not the waiting master) is `PersonStrikeIntent(actor, npc,
  attack option)` and ends the steps too (M38.2: so is a spell with an attack roll, its option
  the opening-strike key `spell:<id>`); a shown cast twin of a boss record is mapped back to
  the boss record first (`menu_scene_view.twin_boss`), so the master's strike stays an offer
  strike.
- Ordering on the running state: each step is turned into acts on the state the steps before it
  leave. In a fight that state is planned here: every command the steps send is probed with the
  real rules (`menu_probe.accepted`, a probe RNG; a draw, a walk) and projected
  (`rules.projection.project_state`), so "move to the crypt, then attack the kobold" plans the
  attack from the crypt (no second walk). Out of a fight the plan keeps the state, and the
  session plans each step again on the live state (`to_groups`, M36.10a: "pick up the salt and
  hand all the salt to Gran Tevin" hands the salt just picked up too).
- The steps stop after an act that ends the line: the turn ends (end turn, flee), a fight starts
  (an offer strike, the offer's Fight, Surprise or Escape answer), or a vote or held parley
  opens (travel, rest, shop, parley).
- Re-validation: the plan is never trusted. The session plays the acts in order through its
  runners, which ask the rules again on the live state (a spent action, a gone item, a foe
  already down are answered plainly there), and stops after a refused act or when the hero's
  turn or the fight ends (M36.6: `session.menu_fight_turn`, `session.menu_turn`). A session that
  wants the dice of an earlier act to count can call `step_acts` per step on the live state.

`resume_strike(state, actor_id, step, regs)`: on the hero's first turn of the fight an offer
strike started, the step's targets are mapped onto the creatures: `foe:<monster>` -> the living
combatants of that monster (`Creature.monster_index`), a master's NPC id -> its creature
(`Creature.npc_id`), the most reachable first (the fight entry's own target order); an entry aimed
at a zone takes the zone holding most of them. The step is then played from the fight menu
(`build_menu`) by the same entry id (the offer menu keeps the fight ids). A strike that no longer
fits (no foe left, the spell gone) is a plain answer.

- Travel steps in a row are one walk to the last place named (M36.10a, `_travels`).

Public API: `Act`, `Group`, `to_acts(state, menu, choice, regs, text="")`, `to_groups(...)`,
`step_acts(state, menu, step, regs, text="")`, `resume_strike(state, actor_id, step, regs)`.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import (
    STRIKE_KINDS,
    ActionKind,
    ActionMenu,
    MenuChoice,
    MenuEntry,
    MenuScope,
    MenuStep,
)
from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import EndTurnCommand, FleeCommand, MoveCommand
from aidm.models.protocol_client import AnswerOffer
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import (
    OfferStrikeIntent,
    OtherIntent,
    ParleyIntent,
    PersonStrikeIntent,
    RefusedIntent,
    RestIntent,
    ShopIntent,
    TravelIntent,
)
from aidm.rules.acts_fight import DrawAttack
from aidm.rules.menu_attacks import drawn_state
from aidm.rules.menu_probe import accepted, walk
from aidm.rules.menu_scene_view import FOE_PREFIX, twin_boss
from aidm.rules.menu_steps_fight import COMMAND_TYPES, FightAct, fight_step_acts
from aidm.rules.menu_steps_scene import SceneAct, free_acts, scene_step_acts
from aidm.rules.menu_unoffered import off_targets
from aidm.rules.projection import project_state

type Act = FightAct | SceneAct
NO_STRIKE = "That strike cannot be made now."
_ENDS = (
    EndTurnCommand,
    FleeCommand,
    OfferStrikeIntent,
    PersonStrikeIntent,
    TravelIntent,
    RestIntent,
    ShopIntent,
    ParleyIntent,
)
_FIGHT_SCOPES = (MenuScope.FIGHT, MenuScope.OFF_TURN)


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry | None:
    return next((e for e in menu.entries if e.id == entry_id), None)


def _ends(act: Act) -> bool:
    if isinstance(act, AnswerOffer):
        return act.choice is not OfferChoice.PARLEY
    return isinstance(act, _ENDS)


def step_acts(
    state: GameState, menu: ActionMenu, step: MenuStep, regs: CombatRegistries, text: str = ""
) -> list[Act]:
    actor_id = menu.actor_id
    entry = _entry(menu, step.entry)
    if entry is None or off_targets(menu, step):  # the validator keeps these out (M38.4: a
        return [OtherIntent(actor_id, text)]  # target the entry cannot act on is never played)
    if menu.scope not in _FIGHT_SCOPES and entry.kind in STRIKE_KINDS:
        strike = _strike_acts(state, actor_id, entry, step)
        if strike is not None:
            return strike
    if menu.scope in _FIGHT_SCOPES:
        free = free_acts(actor_id, entry)
        if free is not None:
            return [*free]
        return [*fight_step_acts(state, actor_id, entry, step, regs)]
    return [*scene_step_acts(state, actor_id, entry, step, text)]


def _strike_acts(
    state: GameState, actor_id: str, entry: MenuEntry, step: MenuStep
) -> list[Act] | None:
    """Out of a fight: a weapon strike at a person here, or a strike at a waiting offer's foes."""
    offer = state.campaign.offer if state.campaign is not None else None
    master = offer.boss_npc_id if offer is not None else None

    def is_person(target: str) -> bool:
        return target in state.world.npcs and target != master

    spell_strike = entry.kind is ActionKind.CAST and entry.option is not None
    pool = entry.target_ids  # M38.2: a spell named at no one is never aimed at a person
    if spell_strike:
        pool = tuple(t for t in pool if not is_person(twin_boss(state, t)))
    chosen = step.targets or (pool if len(pool) == 1 else ())
    targets = tuple(twin_boss(state, t) for t in chosen)
    person = next((t for t in targets if is_person(t)), None)
    if person is not None and (entry.kind is ActionKind.ATTACK or spell_strike):
        return [PersonStrikeIntent(actor_id, person, entry.option)]
    if entry.starts_fight:
        return [OfferStrikeIntent(actor_id, step.model_copy(update={"targets": targets}))]
    return None


def _after(state: GameState, acts: Sequence[Act], regs: CombatRegistries) -> GameState:
    """The fight state the acts leave, as the rules would play them (a refused act changes
    nothing)."""
    for act in acts:
        if isinstance(act, list):
            moves = [m for m in act if isinstance(m, MoveCommand)]
            state = walk(state, moves, regs) or state if len(moves) == len(act) else state
            continue
        command = act
        if isinstance(act, DrawAttack):
            state = drawn_state(state, act.attack.actor_id, act.item, regs.chars) or state
            command = act.attack
        if isinstance(command, COMMAND_TYPES):
            events = accepted(state, command, regs)
            state = project_state(state, events) if events else state
    return state


def _travels(menu: ActionMenu, steps: Sequence[MenuStep]) -> list[MenuStep]:
    """M36.10a: travel steps in a row are one walk to the last place named (the walk goes road by
    road, `TravelIntent(first hop, goal)`); a travel opens a vote and ends the line, so a second
    travel step would never play."""
    kinds = [e.kind if (e := _entry(menu, s.entry)) is not None else None for s in steps]
    return [
        step
        for i, step in enumerate(steps)
        if not (kinds[i] is ActionKind.TRAVEL and i + 1 < len(steps) and kinds[i + 1] is kinds[i])
    ]


type Group = tuple[MenuStep | None, list[Act]]


def to_groups(
    state: GameState,
    menu: ActionMenu,
    choice: MenuChoice,
    regs: CombatRegistries,
    text: str = "",
) -> list[Group]:
    """`to_acts`, grouped by the step each act comes from (None: the `other` part), so a session
    can plan each step again on the state the steps before it left (M36.10a)."""
    other: list[Group] = [(None, [OtherIntent(menu.actor_id, choice.other_text or text)])]
    if not choice.other:
        other = []
    groups: list[Group] = other if choice.other_first else []
    running = state
    for step in _travels(menu, choice.steps):
        made = step_acts(running, menu, step, regs, text)
        groups.append((step, made))
        if any(_ends(a) for a in made):
            return groups
        if menu.scope is MenuScope.FIGHT:
            running = _after(running, made, regs)
    return groups if choice.other_first else [*groups, *other]


def to_acts(
    state: GameState,
    menu: ActionMenu,
    choice: MenuChoice,
    regs: CombatRegistries,
    text: str = "",
) -> list[Act]:
    return [act for _, acts in to_groups(state, menu, choice, regs, text) for act in acts]


def _named(state: GameState, foe: str) -> list[str]:
    """The living creatures a waiting offer's foe target became."""
    enc = state.encounter
    if enc is None:
        return []
    monster = foe[len(FOE_PREFIX) :] if foe.startswith(FOE_PREFIX) else None
    out: list[str] = []
    for cid in enc.combatants:
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or creature.hp <= 0:
            continue
        if (monster is not None and creature.monster_index == monster) or creature.npc_id == foe:
            out.append(cid)
    return out


def _mapped(state: GameState, menu: ActionMenu, entry: MenuEntry, step: MenuStep) -> list[str]:
    named = [cid for foe in step.targets for cid in _named(state, foe)]
    zones = {t.id for t in menu.targets if t.kind == "zone"}
    if entry.target_ids and set(entry.target_ids) <= zones:
        enc = state.encounter
        spots = [enc.combatant(c).zone_id for c in named] if enc is not None else []
        best = sorted(
            (z for z in dict.fromkeys(spots) if z in entry.target_ids),
            key=lambda z: (-spots.count(z), entry.target_ids.index(z)),
        )
        return best[:1]
    order = [t for t in entry.target_ids if t in named]
    return order[: max(1, entry.max_targets)]


def resume_strike(
    state: GameState, actor_id: str, step: MenuStep, regs: CombatRegistries
) -> list[Act]:
    menu = build_menu(state, actor_id, regs)
    entry = _entry(menu, step.entry) if menu.scope is MenuScope.FIGHT else None
    if entry is None:
        return [RefusedIntent(actor_id, NO_STRIKE)]
    targets = _mapped(state, menu, entry, step) if entry.max_targets > 0 else []
    if entry.max_targets > 0 and not targets:
        return [RefusedIntent(actor_id, NO_STRIKE)]
    played = MenuStep(entry=entry.id, targets=tuple(targets), qty=step.qty)
    return step_acts(state, menu, played, regs)
