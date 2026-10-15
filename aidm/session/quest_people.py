"""The table side of quests coming from people (M23.4): the Accept / Not now card and the
"leave these behind?" question before a region is left.

- `answer_quest(core, player, msg)`: the `answer_quest_offer` command, accepted from any seated
  player with a living hero (the rule of the encounter offer card). Accept -> the quest is
  active (`rules.quest_offers.answer_events`), told through `telling.conclude`, which settles
  quests (steps already done count at once). Not now -> the card closes, the quest stays
  offered, one line to the table; the giver asks again on the next arrival. Not now for a
  favour (M23.5) lets it go (`LET_GO`): favours are never asked twice.
- `hold(core, player_id, actor_id, call, prompt)`: store a point-of-no-return call and ask only
  that player (`pending_confirmation`); `confirm_hostile` executes it again confirmed. The travel
  vote's job and the adjudicator's `move_party` both use it for a crossing.
- `CROSS_STAY`: the line told when a crossing is called off.

Public API: `answer_quest`, `hold`, `CROSS_STAY`, `NOT_NOW`, `LET_GO`.
"""

from aidm.dm.llm_types import ToolCall
from aidm.models.protocol_client import AnswerQuestOffer
from aidm.models.protocol_server import ErrorCode, NoticeKind, PendingConfirmationMsg
from aidm.models.quests import QuestKind
from aidm.rules.quest_offers import QuestOfferRefused, answer_events
from aidm.session import combat_flow
from aidm.session.table_core import Player, TableCore
from aidm.session.table_records import PendingHostile
from aidm.session.telling import conclude

CROSS_STAY = "The party stays on this side of the border for now."
NOT_NOW = "{name} says not now; {giver} may ask again another time."
LET_GO = "{name} says not now; {giver} lets the favour go."
NOTHING = "Nobody is asking for your help right now."


def hold(core: TableCore, player_id: str, actor_id: str, call: ToolCall, prompt: str) -> None:
    core.pending = PendingHostile(player_id, actor_id, call, prompt)
    core.send(player_id, PendingConfirmationMsg(player_id=player_id, prompt=prompt))


async def answer_quest(core: TableCore, player: Player, msg: AnswerQuestOffer) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    ask = core.state.world.quest_ask
    asked = core.state.world.quests.get(msg.quest_id)
    favour = asked is not None and asked.kind is QuestKind.FAVOUR
    try:
        events = answer_events(core.state, msg.quest_id, msg.accept)
    except QuestOfferRefused:
        core.error(player.id, ErrorCode.REFUSED, NOTHING)
        return
    core.apply_all(events)
    if not msg.accept:
        npc = core.state.world.npcs.get(ask.npc_id) if ask is not None else None
        giver = npc.name if npc is not None else "they"
        line = LET_GO if favour else NOT_NOW
        core.notice(None, NoticeKind.INFO, line.format(name=pc.name, giver=giver))
        return
    every = await conclude(core, None, events, actor_id=pc.id)
    await combat_flow.after_resolution(core, every)
