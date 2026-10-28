"""THE step executor's pure half: a validated menu choice as the acts the session runners take
(M36.4, SPEC 6.2, docs/next/M36_ACTION_MENU.md). Pure: plans, never applies.

`to_acts(state, menu, choice, regs, text="")` turns the model's pick into the exact act and
command objects the button paths already run (`session.intent_turn.run_intent`,
`session.fight_text`, `combat_flow.player_command`, the client handlers), in the order chosen.
Engine meaning lives here and in `menu_steps_fight` / `menu_steps_scene`, never in wording.
- `other` is one `OtherIntent(actor, text)`: the storyteller's creative or social call, with
  the off-menu part's words (`choice.other_text`, else the whole line). With steps too (M36.5)
  it comes before them when `other_first`, else after them unless a step ended the line.
  A NOT OFFERED thing, in a step or the `other` part, or a step the validator kept out is a
  `RefusedIntent` with the reason (M43.2); a fight spell aimed off its list goes as named
  (`menu_aim.area_aim`: an area spell at the named creature's zone), and so does an area step
  at a zone holding none of the creatures the line names (M44.2, `menu_aim.line_aim`); the
  rules answer it.
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
  opens (travel, rest, shop, parley); M40.1: so does a waiting card's Yes (`card:yes`).
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

- M44.3 (round 9 BB2, BB3, BB12): one buy is one payment, a named ware is bought or refused
  (`menu_buy`); a talk offering gold over the purse (`menu_unoffered.gold_refusal`, in an
  `other` part or a pay) is refused before the talk, so the offer moves no attitude.
- Travel steps in a row are one walk to the last place named (M36.10a, `_travels`).
- M41.3 (round 7 Z6: "we trudge back to the Rust Chapel and I search the iron walls" only
  travelled): `plan_line` keeps what an act that ends the line cut off (`Plan.rest`: the steps
  after it and an `other` part said after them) with the reason it waits (`Plan.why`, by the
  act: "the fight has started"), never a silent drop. The session plays the rest once a travel,
  rest or shop the party agreed to is done, on the menu of the place it reached (`refit`: the steps
  that still fit, in order, and why the first that does not cannot be done now), else tells it.
- M41.3 (Z7): a shared step (a search, a pickup) with `by` naming one of `ActionMenu.helpers`
  is played as that hero (`step_actor`).

Public API: `UNKNOWN_STEP`, `Act`, `Group`, `Plan`, `to_acts(state, menu, choice, regs, text="")`,
`to_groups(...)`, `plan_line(...)`, `refit(menu, before, rest)`, `step_actor(menu, step)`,
`step_acts(state, menu, step, regs, text="")`, `resume_strike(state, actor_id, step, regs)`.
"""

from collections.abc import Sequence
from dataclasses import dataclass

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
from aidm.models.protocol_client import AnswerOffer, ConfirmHostile
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
from aidm.rules.menu_aim import area_aim, line_aim, zones_held
from aidm.rules.menu_attacks import drawn_state
from aidm.rules.menu_buy import absorbed, named_buy, one_payment
from aidm.rules.menu_probe import accepted, walk
from aidm.rules.menu_scene_view import FOE_PREFIX, twin_boss
from aidm.rules.menu_steps_fight import COMMAND_TYPES, FightAct, fight_step_acts
from aidm.rules.menu_steps_scene import SceneAct, free_acts, scene_step_acts
from aidm.rules.menu_unoffered import (
    as_entry,
    engine_answers,
    gold_refusal,
    off_targets,
    other_refusal,
    refusal,
)
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
    ConfirmHostile,
)
_FIGHT_SCOPES = (MenuScope.FIGHT, MenuScope.OFF_TURN)
FIGHT_FIRST = "the fight has started"
_WHY: dict[type[object], str] = {  # M41.3: why the rest of a line waits after an act that ends it
    EndTurnCommand: "your turn is over",
    FleeCommand: "you have left the fight",
    OfferStrikeIntent: FIGHT_FIRST,
    PersonStrikeIntent: FIGHT_FIRST,
    ConfirmHostile: FIGHT_FIRST,
    TravelIntent: "the party travels first",
    RestIntent: "the party rests first",
    ShopIntent: "the shop opens first",
    ParleyIntent: "the parley is answered first",
    AnswerOffer: "the offer is answered first",
}
CANNOT_NOW = "{what} cannot be done now"
UNKNOWN_STEP = "That cannot be done now."  # M43.2: a step at no entry of the menu


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry | None:
    return next((e for e in menu.entries if e.id == entry_id), None)


def _kind(menu: ActionMenu, step: MenuStep) -> ActionKind | None:
    entry = _entry(menu, step.entry)
    return entry.kind if entry is not None else None


def _ends(act: Act) -> bool:
    if isinstance(act, AnswerOffer):
        return act.choice is not OfferChoice.PARLEY
    return isinstance(act, _ENDS)


def step_actor(menu: ActionMenu, step: MenuStep) -> str:
    """M41.3: the hero who does the step: `by` on a shared entry naming a helper, else the
    acting hero."""
    entry = _entry(menu, step.entry)
    shared = entry is not None and entry.shared and step.by in menu.helpers
    return step.by if shared and step.by is not None else menu.actor_id


def step_acts(
    state: GameState, menu: ActionMenu, step: MenuStep, regs: CombatRegistries, text: str = ""
) -> list[Act]:
    actor_id = step_actor(menu, step)
    entry = _entry(menu, step.entry)
    why = refusal(menu, step)  # M43.2 (B2)
    if why is not None or entry is None:
        return [RefusedIntent(actor_id, why or UNKNOWN_STEP)]
    if engine_answers(menu, step):  # M43.2 (B3): the real command answers, never a stand-in
        step = area_aim(state, entry, step)
    elif off_targets(menu, step):  # the validator keeps these out; never played (M38.4)
        return [RefusedIntent(actor_id, f"{CANNOT_NOW.format(what=entry.label)}.")]  # (M43.2)
    if menu.scope not in _FIGHT_SCOPES and entry.kind in STRIKE_KINDS:
        strike = _strike_acts(state, actor_id, entry, step)
        if strike is not None:
            return strike
    if menu.scope in _FIGHT_SCOPES:
        free = free_acts(actor_id, entry)
        if free is not None:
            return [*free]
        step = line_aim(state, menu, entry, step, text)  # M44.2 (B3): never a stand-in zone
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


@dataclass(frozen=True)
class Plan:
    """M41.3: a line's acts by step, and what an act that ends the line cut off (with why)."""

    groups: list[Group]
    rest: MenuChoice | None = None
    why: str = ""


def _rest(choice: MenuChoice, steps: Sequence[MenuStep]) -> MenuChoice | None:
    late = choice.other and not choice.other_first
    if not steps and not late:
        return None
    text = choice.other_text if late else ""
    return MenuChoice(steps=tuple(steps), other=late, other_text=text)


def _other_group(state: GameState, menu: ActionMenu, words: str, regs: CombatRegistries) -> Group:
    """The `other` part. M43.2 (B2): a NOT OFFERED thing it names is refused with the reason; in
    a fight a weapon, spell or feature it names at a creature or area it names is that entry
    (`menu_unoffered.as_entry`); only the rest goes to the storyteller."""
    why = other_refusal(menu, words)
    if why is not None:
        return None, [RefusedIntent(menu.actor_id, why)]
    step = as_entry(menu, words) or named_buy(menu, words, dear=True)  # M44.3 (BB3)
    if step is not None:
        return step, step_acts(state, menu, step, regs, words)
    return None, [OtherIntent(menu.actor_id, words)]


def plan_line(
    state: GameState,
    menu: ActionMenu,
    choice: MenuChoice,
    regs: CombatRegistries,
    text: str = "",
) -> Plan:
    """The acts grouped by the step each act comes from (None: the `other` part), so a session
    can plan each step again on the state the steps before it left (M36.10a)."""
    words = choice.other_text or text
    chosen = one_payment(state, menu, choice.steps, text)  # M44.3 (BB2): one buy, one payment
    if choice.other and absorbed(menu, chosen, words):
        choice = MenuChoice(steps=chosen, colour=choice.colour)
    other = [_other_group(state, menu, words, regs)] if choice.other else []
    groups: list[Group] = other if choice.other_first else []
    kinds = {_kind(menu, s) for s in chosen}
    offers = ActionKind.TALK in kinds and (choice.other or ActionKind.PAY in kinds)
    unpaid = gold_refusal(menu) if offers else None
    if unpaid is not None:  # M44.3 (BB12): a sum offered in talk the hero cannot pay: refused first
        groups.insert(0, (None, [RefusedIntent(menu.actor_id, unpaid)]))
    running = state
    steps = _travels(menu, chosen)
    for index, step in enumerate(steps):
        made = step_acts(running, menu, step, regs, text)
        groups.append((step, made))
        ender = next((a for a in made if _ends(a)), None)
        if ender is not None:
            rest = _rest(choice, steps[index + 1 :])
            return Plan(groups, rest, _WHY.get(type(ender), FIGHT_FIRST) if rest else "")
        if menu.scope is MenuScope.FIGHT:
            running = _after(running, made, regs)
    return Plan(groups if choice.other_first else [*groups, *other])


def to_groups(
    state: GameState,
    menu: ActionMenu,
    choice: MenuChoice,
    regs: CombatRegistries,
    text: str = "",
) -> list[Group]:
    return plan_line(state, menu, choice, regs, text).groups


def _fits(menu: ActionMenu, step: MenuStep) -> bool:
    entry = _entry(menu, step.entry)
    if entry is None or any(t not in entry.target_ids for t in step.targets):
        return False
    return step.by is None or step_actor(menu, step) == step.by


def refit(menu: ActionMenu, before: ActionMenu, rest: MenuChoice) -> tuple[MenuChoice | None, str]:
    """M41.3: the rest of a line on the menu of where the party is now: the steps that still fit,
    in order, up to the first that does not (and why that one cannot be done now: its label on
    the menu it was chosen from); the `other` part only when every step fits."""
    for index, step in enumerate(rest.steps):
        if not _fits(menu, step):
            old = _entry(before, step.entry)
            why = CANNOT_NOW.format(what=old.label if old is not None else step.entry)
            kept = rest.steps[:index]
            return (MenuChoice(steps=kept) if kept else None), why
    return rest, ""


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
    spots = zones_held(state, entry, zones, named)
    if spots is not None:
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
