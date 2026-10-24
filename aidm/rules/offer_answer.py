"""Answering an encounter offer: fight, surprise, escape or parley (SPEC 9). Pure.

The checks use the DCs the offer carries (set from the region tier by data, never by the AI):
- fight: the fight starts.
- surprise: a group Stealth check; success -> the foes are surprised; either way the fight starts.
- escape: a group check, each PC rolling the better of Stealth and Athletics; success -> the
  party slips back to where it came from (no fight; a carried light still gives a dark place
  away, `aidm.rules.light.arrival_events`); failure -> the fight starts.
- parley: one PC (the actor, else the first living PC) rolls Persuasion (or Intimidation, or
  Deception, M29.7a);
  success -> no fight (with a boss: Persuasion improves its attitude, social contribution only,
  capped and floored); failure -> the fight starts. A master whose Peace route is done hears the
  party out: the parley holds without a roll (M29.7c R14, `sure_parley`); the route's deeds then
  win the master over (`quest_progress`).
M31.1b V11: a won parley with a master whose Peace route is not done buys peace for now only:
the offer closes with a plain line (`MASTER_WAITS`: the way on is not yet open; finish the route
or face the master) and the master offers again on the next arrival (`encounter_offer`).
Group checks follow SRD 5.1 "Group Checks": the group succeeds when at least half succeed.
A boss offer whose region is already resolved (an old save from before M29.5b G29) closes
peacefully whatever the answer: an allied boss is never turned hostile by it.
M29.9a T8: an offer whose foes are all dead or gone never starts a fight (`foes_gone`: the boss
died, or a finished fight at the offer's place downed every monster the offer lists); any answer
closes it with "no foes are left" (an old save kept such an offer open and respawned the foe).

Public API: `OfferRefused`; `answer_offer(state, choice, data, rng, *, actor_id=None,
skill=None) -> list[AnyEvent]` (starts with `OfferResolved`; `CheckResolved` per roll);
`sure_parley(state, offer) -> bool`; `foes_gone(state, offer) -> bool`;
`master_waits(state, offer) -> str | None`; `MASTER_WAITS`.
"""

from collections import Counter
from collections.abc import Sequence

from aidm.models.abilities import Skill
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.checks import CheckResult
from aidm.models.dm_tiers import DeltaTier
from aidm.models.encounter import EncounterStatus, Side, SurpriseKind
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.quests import RouteKind
from aidm.models.state import Creature, GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.checks import skill_bonus
from aidm.rules.conditions import skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.encounter_offer import offer_fight_events
from aidm.rules.light import arrival_events
from aidm.rules.offer_spokes import OfferData
from aidm.rules.progression import peaceful_close, region_of, settled_offer
from aidm.rules.quest_plan import main_quest
from aidm.rules.quest_progress import peace_ready
from aidm.rules.social import social_attitude_events

MASTER_WAITS = (
    "{master} lets you be for now, but the way on is not yet open: finish {route}, or face {master}"
)
PARLEY_SKILLS = (Skill.PERSUASION, Skill.INTIMIDATION, Skill.DECEPTION)
ESCAPE_SKILLS = (Skill.STEALTH, Skill.ATHLETICS)


class OfferRefused(ValueError):
    """No offer is pending, or the answer does not fit it."""


def _pcs(state: GameState) -> list[Creature]:
    pcs = [c for c in state.creatures.values() if c.pc is not None and not c.dead and c.hp > 0]
    return sorted(pcs, key=lambda c: c.id)


def _best(creature: Creature, skills: Sequence[Skill]) -> Skill:
    return max(skills, key=lambda s: (skill_bonus(creature, s), -skills.index(s)))


def _group(
    state: GameState, rng: Rng, skills: Sequence[Skill], dc: int, reason: str
) -> tuple[bool, list[AnyEvent]]:
    events: list[AnyEvent] = []
    results: list[CheckResult] = []
    for pc in _pcs(state):
        result = skill_check_with_conditions(rng, pc, _best(pc, skills), dc)
        results.append(result)
        events.append(CheckResolved(creature_id=pc.id, result=result, reason=reason))
    wins = sum(1 for r in results if r.success)
    return bool(results) and wins * 2 >= len(results), events


def _speaker(state: GameState, actor_id: str | None) -> Creature:
    pcs = _pcs(state)
    chosen = next((c for c in pcs if c.id == actor_id), pcs[0] if pcs else None)
    if chosen is None:
        raise OfferRefused("no living player character can speak")
    return chosen


def _parley(
    state: GameState, offer: EncounterOffer, rng: Rng, actor_id: str | None, skill: Skill | None
) -> tuple[bool, list[AnyEvent]]:
    used = skill or Skill.PERSUASION
    if used not in PARLEY_SKILLS:
        raise OfferRefused(f"parley uses {' or '.join(s.value for s in PARLEY_SKILLS)}")
    if sure_parley(state, offer):
        return True, []
    speaker = _speaker(state, actor_id)
    result = skill_check_with_conditions(rng, speaker, used, offer.parley_dc)
    events: list[AnyEvent] = [CheckResolved(creature_id=speaker.id, result=result, reason="parley")]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if result.success and boss is not None and used is Skill.PERSUASION:
        events.extend(social_attitude_events(boss, DeltaTier.IMPROVE, "a successful parley"))
    return result.success, events


def master_waits(state: GameState, offer: EncounterOffer) -> str | None:
    """V11: the line of a won parley with a master before the Peace route is done (None: no
    master)."""
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    region = region_of(state, offer.node_id)
    campaign = state.campaign
    if boss is None or region is None or campaign is None:
        return None
    act = next((a for a in campaign.plan.acts if a.region.id == region.id), None)
    routes = main_quest(campaign.plan, act.index).routes if act is not None else ()
    peace = next((r for r in routes if r.kind is RouteKind.PEACE), None)
    route = f"the peaceful way ({peace.title})" if peace is not None else "the peaceful way"
    return MASTER_WAITS.format(master=boss.name, route=route)


def sure_parley(state: GameState, offer: EncounterOffer) -> bool:
    """A master whose Peace route is done hears the party out: the parley holds without a roll
    (M29.7c R14; shown as sure on the offer card). So does a master already won over (M29.9a
    T15: the alliance leaves the offer waiting for the player's answer)."""
    region = region_of(state, offer.node_id)
    if offer.boss_npc_id is None or region is None:
        return False
    return settled_offer(state) is not None or peace_ready(state, region)


def foes_gone(state: GameState, offer: EncounterOffer) -> bool:
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        return boss.dead
    enc = state.encounter
    if enc is None or enc.status is EncounterStatus.ACTIVE or enc.node_id != offer.node_id:
        return False
    downed: Counter[str] = Counter()
    for combatant in enc.combatants.values():
        creature = state.creatures.get(combatant.creature_id)
        if combatant.side is not Side.HOSTILE or creature is None or creature.monster_index is None:
            continue
        if creature.dead or creature.hp <= 0 or combatant.withdrawn is not None:
            downed[creature.monster_index] += 1
    return bool(offer.monster_ids) and Counter(offer.monster_ids) <= downed


def _resolve(
    state: GameState,
    offer: EncounterOffer,
    choice: OfferChoice,
    rng: Rng,
    args: tuple[str | None, Skill | None],
) -> tuple[bool | None, list[AnyEvent], SurpriseKind | None]:
    """(success, check events, the fight's surprise kind or None when no fight starts)."""
    if choice is OfferChoice.FIGHT:
        return None, [], SurpriseKind.NONE
    if choice is OfferChoice.SURPRISE:
        ok, events = _group(state, rng, (Skill.STEALTH,), offer.surprise_dc, "surprise attack")
        return ok, events, SurpriseKind.HOSTILE if ok else SurpriseKind.NONE
    if choice is OfferChoice.ESCAPE:
        ok, events = _group(state, rng, ESCAPE_SKILLS, offer.escape_dc, "escape")
        return ok, events, None if ok else SurpriseKind.NONE
    ok, events = _parley(state, offer, rng, *args)
    return ok, events, None if ok else SurpriseKind.NONE


def answer_offer(
    state: GameState,
    choice: OfferChoice,
    data: OfferData,
    rng: Rng,
    *,
    actor_id: str | None = None,
    skill: Skill | None = None,
) -> list[AnyEvent]:
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    if offer is None:
        raise OfferRefused("no encounter is waiting for an answer")
    if choice not in offer.options:
        raise OfferRefused(f"{choice.value} is not an option here")
    if settled_offer(state) is not None:  # M29.5b G29: the boss's region is already settled
        return [peaceful_close(offer)]
    if foes_gone(state, offer):
        return [
            OfferResolved(
                offer_id=offer.id,
                choice=choice,
                detail="no foes are left",
                foes=offer.monster_ids,
            )
        ]
    sure = choice is OfferChoice.PARLEY and sure_parley(state, offer)
    success, checks, surprise = _resolve(state, offer, choice, rng, (actor_id, skill))
    detail = "the fight starts" if surprise is not None else "no fight"
    if success and choice is OfferChoice.PARLEY and not sure:
        detail = master_waits(state, offer) or detail
    events: list[AnyEvent] = [
        OfferResolved(
            offer_id=offer.id,
            choice=choice,
            success=success,
            detail=detail,
            foes=offer.monster_ids,
        ),
        *checks,
    ]
    if surprise is not None:
        events.extend(offer_fight_events(state, offer, data, rng, surprise))
    elif choice is OfferChoice.ESCAPE and offer.retreat_node is not None:
        world = state.world
        events.append(
            PartyMoved(
                from_node=world.current_node,
                to_node=offer.retreat_node,
                scene_index=world.scene_index + 1,
            )
        )
        events.extend(arrival_events(state, offer.retreat_node))
    return events
