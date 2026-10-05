"""Answering an encounter offer: fight, surprise, escape or parley (SPEC 9). Pure.

The checks use the DCs the offer carries (set from the region tier by data, never by the AI):
- fight: the fight starts.
- surprise: a group Stealth check; success -> the foes are surprised; either way the fight starts.
- escape: a group check, each PC rolling the better of Stealth and Athletics; success -> the
  party slips back to where it came from (no fight); failure -> the fight starts.
- parley: one PC (the actor, else the first living PC) rolls Persuasion (or Intimidation);
  success -> no fight (with a boss: Persuasion improves its attitude, social contribution only,
  capped and floored); failure -> the fight starts.
Group checks follow SRD 5.1 "Group Checks": the group succeeds when at least half succeed.

Public API: `OfferRefused`; `answer_offer(state, choice, data, rng, *, actor_id=None,
skill=None) -> list[AnyEvent]` (starts with `OfferResolved`; `CheckResolved` per roll).
"""

from collections.abc import Sequence

from aidm.models.abilities import Skill
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.checks import CheckResult
from aidm.models.dm_tiers import DeltaTier
from aidm.models.encounter import SurpriseKind
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import Creature, GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.checks import skill_bonus
from aidm.rules.conditions import skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.encounter_offer import OfferData, offer_fight_events
from aidm.rules.social import social_attitude_events

PARLEY_SKILLS = (Skill.PERSUASION, Skill.INTIMIDATION)
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
    speaker = _speaker(state, actor_id)
    result = skill_check_with_conditions(rng, speaker, used, offer.parley_dc)
    events: list[AnyEvent] = [CheckResolved(creature_id=speaker.id, result=result, reason="parley")]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if result.success and boss is not None and used is Skill.PERSUASION:
        events.extend(social_attitude_events(boss, DeltaTier.IMPROVE, "a successful parley"))
    return result.success, events


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
    success, checks, surprise = _resolve(state, offer, choice, rng, (actor_id, skill))
    detail = "the fight starts" if surprise is not None else "no fight"
    events: list[AnyEvent] = [
        OfferResolved(offer_id=offer.id, choice=choice, success=success, detail=detail),
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
    return events
