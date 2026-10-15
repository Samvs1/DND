"""After every mechanics batch: regions, milestones, then quests (M23.2, ONE helper).

The session runs `settle_after` wherever a batch of mechanics was applied (a fight's end in
`combat_flow.finish_fight`, every exploration resolution in `telling.follow_ups`), so a step
done by a move, a pick-up, a fight or an attitude change moves its quest at once. Order:
1. `quest_rewards.resolution_reward_events` (region resolution + milestone rewards);
2. `milestones.milestone_events` of the batch (first visit, cleared spoke);
3. passes of `quest_progress.quest_progress_events`, each followed by region resolution, until a
   pass moves nothing (at most `MAX_PASSES`): a finished Peace route allies the boss, the
   alliance resolves the region, and the main quest completes, all in the same batch;
4. once a pass moved nothing (M23.4, `rules.quest_offers` / `rules.quest_leaving`): the open
   tasks of a region the party left close as left behind (a task whose steps were all done
   completed in step 3 first), an offered favour whose card is gone lapses (M23.5,
   `rules.favours`), then the giver here asks (only on an arrival in the batch), then the leads
   of the party's region.
Every pass reads the applied state, so nothing is paid twice; whatever the pass bound leaves
is picked up by the next batch.

Public API: `MAX_PASSES`, `settle_after(state, regs, batch, apply_all) -> list[AnyEvent]` (the
applied follow-up events, in order).
"""

from collections.abc import Callable, Sequence

from aidm.dm.tool_context import ToolRegistries
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.favours import favour_lapse_events
from aidm.rules.milestones import milestone_events
from aidm.rules.quest_leaving import left_behind_events
from aidm.rules.quest_offers import ask_events, lead_events
from aidm.rules.quest_progress import quest_progress_events
from aidm.rules.quest_rewards import resolution_reward_events

MAX_PASSES = 8

type ApplyAll = Callable[[list[AnyEvent]], list[AnyEvent]]


def settle_after(
    state: GameState, regs: ToolRegistries, batch: Sequence[AnyEvent], apply_all: ApplyAll
) -> list[AnyEvent]:
    tiers, catalogue = regs.tiers, regs.catalogue
    out = apply_all(resolution_reward_events(state, tiers, catalogue))
    out += apply_all(milestone_events(state, [*batch, *out], tiers, catalogue))
    for _ in range(MAX_PASSES):
        moved = apply_all(quest_progress_events(state, tiers, catalogue))
        if not moved:
            break
        out += moved
        out += apply_all(resolution_reward_events(state, tiers, catalogue))
    else:
        return out  # still moving: the people part waits for the next batch
    out += apply_all(left_behind_events(state))
    out += apply_all(favour_lapse_events(state))
    out += apply_all(ask_events(state, [*batch, *out]))
    out += apply_all(lead_events(state))
    return out
