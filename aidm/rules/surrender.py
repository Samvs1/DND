"""Demanding surrender in a fight (M29.9a T12, owner rule: a possible action is never refused and
data adds effects; DECISIONS M29.9a). Pure: returns events.

`demand_surrender(rng, state, actor_id, skill, tiers)`: the hero spends the action and rolls
Intimidation or Persuasion (`SURRENDER_SKILLS`) against `surrender_dc`. On a success every
standing hostile of the fight that is not already held by the party gets the data condition
"surrendered" from the hero (`rules.condition_timing.apply_condition`: creature types the
condition spares, the mindless, and the condition-immune keep fighting). Its data does the rest:
no actions, movement or reactions; a blow from the party ends it (`rules.harm_ends`, a surface or
a burn already set does not); a fight whose remaining hostiles all surrendered or were befriended
ends as a victory, and surrendered foes count as defeated (kill XP, loot, a master beaten:
`rules.encounter`, `rules.progression`).

`surrender_dc(state, tiers)`: the parley DC of the region tier (`DmTiers.offer_dc_tiers`, the
boss table when a region master stands among the foes), `surrender_unbeaten_steps` tiers harder
while no foe has fallen and the foes keep more than half their hit points.

Public API: `SURRENDER_SKILLS`, `SURRENDERED`, `surrender_dc`, `demand_surrender`.
"""

from aidm.data.dm_tiers import DmTiers
from aidm.models.abilities import Skill
from aidm.models.checks import DcTier
from aidm.models.encounter import Combatant, Side
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import GameState
from aidm.rules.checks import dc_for_tier
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.encounter import active_encounter, is_standing
from aidm.rules.harm_ends import befriended_by_party
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.turns import spend_action

SURRENDER_SKILLS = (Skill.INTIMIDATION, Skill.PERSUASION)
SURRENDERED = "surrendered"
_TIERS = list(DcTier)


def _hostiles(state: GameState) -> list[Combatant]:
    enc = active_encounter(state)
    return [c for c in enc.combatants.values() if c.side is Side.HOSTILE]


def _unbeaten(state: GameState, hostiles: list[Combatant]) -> bool:
    standing = [c for c in hostiles if is_standing(state, c)]
    if len(standing) < len(hostiles):
        return False
    left = sum(state.creatures[c.creature_id].hp for c in standing)
    whole = sum(state.creatures[c.creature_id].max_hp for c in hostiles)
    return left * 2 > whole


def _master_among(state: GameState, hostiles: list[Combatant]) -> bool:
    campaign = state.campaign
    if campaign is None:
        return False
    masters = {boss_npc_id(r) for r in campaign.plan.all_regions()}
    return any(state.creatures[c.creature_id].npc_id in masters for c in hostiles)


def surrender_dc(state: GameState, tiers: DmTiers) -> int:
    hostiles = _hostiles(state)
    table = tiers.boss_parley_dc_tiers if _master_among(state, hostiles) else tiers.offer_dc_tiers
    tier = DcTier(table.get(str(state.world.region_tier), DcTier.MEDIUM.value))
    if _unbeaten(state, hostiles):
        step = min(len(_TIERS) - 1, _TIERS.index(tier) + tiers.surrender_unbeaten_steps)
        tier = _TIERS[step]
    return dc_for_tier(tier)


def demand_surrender(
    rng: Rng, state: GameState, actor_id: str, skill: Skill, tiers: DmTiers
) -> list[AnyEvent]:
    if skill not in SURRENDER_SKILLS:
        raise ValueError(f"a surrender is demanded with {SURRENDER_SKILLS}, not {skill}")
    events: list[AnyEvent] = spend_action(state, actor_id, reason="demand surrender")
    result = skill_check_with_conditions(
        rng, state.creatures[actor_id], skill, surrender_dc(state, tiers)
    )
    events.append(CheckResolved(creature_id=actor_id, result=result, reason="surrender"))
    if not result.success:
        return events
    for combatant in _hostiles(state):
        if not is_standing(state, combatant) or befriended_by_party(state, combatant.creature_id):
            continue
        mark = new_condition(SURRENDERED, source_id=actor_id)
        events.extend(apply_condition(state.creatures[combatant.creature_id], mark))
    return events
