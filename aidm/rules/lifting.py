"""Lifting a keepsake back from an NPC (M29.7a R18: a natural-20 Sleight of Hand to take back the
Bailiff's Broken Link was told as done, and no item moved). Pure: returns events.

`lift_events(state, pc_id, npc_id, keepsake_id, rng, tiers)`: the NPC must be here and alive and
hold that keepsake (`WorldNpc.keepsakes`: the engine only knows what was handed to them). The hero
rolls Sleight of Hand through the ordinary check (`rules.gear_checks.gear_check`: conditions,
gear boons) against the medium tier, capped by the region (`dm_tiers.check_dc_tier_cap`;
RULES_DECISIONS M29.7a). Success: `KeepsakeTaken` moves it to the hero. Failure: the NPC notices
(`social_attitude_events`, a worsening; nothing moves). Refusals are plain `LiftRefused`.

Public API: `LiftRefused(detail)`, `lift_events(...) -> list[AnyEvent]`.
"""

from aidm.data.dm_tiers import DmTiers
from aidm.models.abilities import Skill
from aidm.models.checks import DcTier
from aidm.models.dm_tiers import DeltaTier
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.quest_events import KeepsakeTaken
from aidm.models.state import GameState
from aidm.rules.checks import dc_for_tier
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import capped_dc_tier
from aidm.rules.gear_checks import gear_check
from aidm.rules.social import social_attitude_events


class LiftRefused(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def lift_events(
    state: GameState, pc_id: str, npc_id: str, keepsake_id: str, rng: Rng, tiers: DmTiers
) -> list[AnyEvent]:
    pc = state.creatures.get(pc_id)
    npc = state.world.npcs.get(npc_id)
    if pc is None or pc.pc is None or pc.dead or pc.hp <= 0:
        raise LiftRefused("Your hero cannot do that right now.")
    if npc is None or npc.dead or npc.node_id != state.world.current_node:
        raise LiftRefused("Nobody here holds that.")
    keepsake = next((k for k in npc.keepsakes if k.id == keepsake_id), None)
    if keepsake is None:
        raise LiftRefused(f"{npc.name} does not hold that.")
    tier = capped_dc_tier(tiers, DcTier.MEDIUM, state.world.region_tier)
    result = gear_check(rng, state, pc, Skill.SLEIGHT_OF_HAND, dc_for_tier(tier))
    result = result.model_copy(update={"tier": tier})
    reason = f"Lift the {keepsake.name} from {npc.name}"
    events: list[AnyEvent] = [CheckResolved(creature_id=pc.id, result=result, reason=reason)]
    if result.success:
        events.append(KeepsakeTaken(creature_id=pc.id, keepsake_id=keepsake.id, npc_id=npc.id))
    else:
        caught = f"caught {pc.name} reaching for the {keepsake.name}"
        events += social_attitude_events(npc, DeltaTier.WORSEN, caught)
    return events
