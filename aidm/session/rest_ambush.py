"""A rest started while a foe's encounter offer waits here (M35.2, round 6 Y4: a long rest was
taken in front of a waiting master, and the story said he "has not moved").

`ambushed(core) -> bool`: with a foe waiting where the party stands
(`rules.waiting_foe.waiting_foe`), the rest is not taken and the foe takes the opening
(`rest_ambush_events`: the offer is answered as a fight with the party surprised). The table is
shown one plain line (`REST_AMBUSHED`), the story tells the fight's start and the fight runs as
any other (`combat_flow.after_resolution`). False (nothing done) when no foe waits. Every rest
path asks first: the Rest buttons and typed rests (`party_actions.rest_job`, short and long) and
the long rest with long-rest crafts (`gear_actions.rest_with_crafts`).

Public API: `REST_AMBUSHED`, `ambushed`.
"""

from collections import Counter

from aidm.dm.arrival import offer_data
from aidm.dm.entities import display_name
from aidm.dm.wording import counted
from aidm.models.campaign_state import EncounterOffer
from aidm.models.protocol_server import NoticeKind
from aidm.models.state import GameState
from aidm.rules.waiting_foe import rest_ambush_events, waiting_foe
from aidm.session import combat_flow
from aidm.session.table_core import TableCore
from aidm.session.telling import conclude

REST_AMBUSHED = (
    "You start to make camp, but {foes} will not wait while you rest. "
    "No rest is taken: the fight starts at once, and your party is caught off guard."
)


def _foes(state: GameState, offer: EncounterOffer) -> str:
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        return boss.name
    counts = Counter(offer.monster_ids)
    names = [counted(display_name(m).lower(), n) for m, n in counts.items()]
    return " and ".join(names) if names else "the foes here"


async def ambushed(core: TableCore) -> bool:
    offer = waiting_foe(core.state)
    if offer is None:
        return False
    foes = _foes(core.state, offer)
    events = core.apply_all(rest_ambush_events(core.state, offer_data(core.regs), core.rng))
    core.notice(None, NoticeKind.INFO, REST_AMBUSHED.format(foes=foes))
    every = await conclude(core, None, events)
    await combat_flow.after_resolution(core, every)
    return True
