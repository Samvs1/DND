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

M31.1a V5 (round 4: a demand made of the undead Tithekeeper rolled a natural 20 that did
nothing): when every standing foe is of a kind the condition spares (`spares_types`: undead,
constructs, oozes, plants), `demand_surrender` raises `NoneYield` with a plain line before
anything is spent ("The Tithekeeper will not yield: the dead do not surrender.", the reason from
the condition's `spares_why`); when only some never yield, the roll covers the others and
`never_yield_line` names the rest.

M32.1a X5 (round 5: "Drop your weapons and yield!" to a risen zombie while its offer waited rolled
Intimidation and was told obeyed): `offer_never_yield_line(state, monsters)` is the same plain
line for the foes of the waiting encounter offer before any fight (their SRD type, or the
master's archetype), None when any of them could yield.

Public API: `SURRENDER_SKILLS`, `SURRENDERED`, `NoneYield`, `surrender_dc`, `never_yield_line`,
`offer_never_yield_line`, `demand_surrender`.
"""

from aidm.data.dm_tiers import DmTiers
from aidm.data.registry import Registry
from aidm.data.srd_monsters import SrdMonster
from aidm.models.abilities import Skill
from aidm.models.checks import DcTier
from aidm.models.encounter import Combatant, Side
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import Creature, GameState
from aidm.rules.checks import dc_for_tier
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import condition_def, skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.encounter import active_encounter, is_standing
from aidm.rules.harm_ends import befriended_by_party
from aidm.rules.monster_stats import creature_type_of
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


class NoneYield(Exception):
    """Every standing foe is of a kind that never yields: no roll, the action is kept."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.line = line


def _standing_foes(state: GameState) -> list[Creature]:
    return [
        state.creatures[c.creature_id]
        for c in _hostiles(state)
        if is_standing(state, c) and not befriended_by_party(state, c.creature_id)
    ]


def _yields(creature: Creature, actor_id: str) -> bool:
    return bool(apply_condition(creature, new_condition(SURRENDERED, source_id=actor_id)))


def _called(creature: Creature) -> str:
    return creature.name if creature.npc_id else f"the {creature.name.lower()}"


def _line(names: list[str], kind: str) -> str:
    who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    why = condition_def(SURRENDERED).spares_why.get(kind)
    line = f"{who[:1].upper()}{who[1:]} will not yield"
    return f"{line}: {why}." if why else f"{line}."


def never_yield_line(state: GameState, actor_id: str) -> str | None:
    """The plain line for the standing foes that never yield (M31.1a V5): "The Tithekeeper will
    not yield: the dead do not surrender." None when every standing foe can yield."""
    stubborn = [c for c in _standing_foes(state) if not _yields(c, actor_id)]
    if not stubborn:
        return None
    return _line([_called(c) for c in stubborn], creature_type_of(stubborn[0]))


def offer_never_yield_line(state: GameState, monsters: Registry[SrdMonster]) -> str | None:
    """The plain line when every foe of the waiting offer is of a kind that never yields."""
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is None:
        return None
    foes = [
        (f"the {m.name.lower()}", m.type.lower())
        for i in offer.monster_ids
        if (m := monsters.find(i))
    ]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    master = monsters.find(boss.archetype_id) if boss is not None and boss.archetype_id else None
    if boss is not None and master is not None:
        foes.append((boss.name, master.type.lower()))
    spared = condition_def(SURRENDERED).spares_types
    if not foes or any(kind not in spared for _, kind in foes):
        return None
    names = list(dict.fromkeys(name for name, _ in foes))
    return _line(names, foes[0][1])


def demand_surrender(
    rng: Rng, state: GameState, actor_id: str, skill: Skill, tiers: DmTiers
) -> list[AnyEvent]:
    if skill not in SURRENDER_SKILLS:
        raise ValueError(f"a surrender is demanded with {SURRENDER_SKILLS}, not {skill}")
    foes = _standing_foes(state)
    if foes and not any(_yields(c, actor_id) for c in foes):
        raise NoneYield(never_yield_line(state, actor_id) or "")
    events: list[AnyEvent] = spend_action(state, actor_id, reason="demand surrender")
    result = skill_check_with_conditions(
        rng, state.creatures[actor_id], skill, surrender_dc(state, tiers)
    )
    events.append(CheckResolved(creature_id=actor_id, result=result, reason="surrender"))
    if not result.success:
        return events
    for foe in foes:
        events.extend(apply_condition(foe, new_condition(SURRENDERED, source_id=actor_id)))
    return events
