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
- `choose_finale(core, player, msg)` (M23.9): the finale card, from the same players as the quest
  card. The phone asks "Are you sure? This ends the story." itself and sends `confirm: true`;
  without it nothing happens but that question back to the sender (no event). Confirmed ->
  `FinaleChosen`, told through `conclude` (the chosen ending as an engine fact), whose
  `maybe_epilogue` then runs the campaign-complete path (Scribe line, epilogue, victory).

Public API: `answer_quest`, `hold`, `choose_finale`, `CROSS_STAY`, `NOT_NOW`, `LET_GO`,
`SURE`, `NO_FINALE`.
"""

from aidm.dm.llm_types import ToolCall
from aidm.models.protocol_client import AnswerQuestOffer, ChooseFinale
from aidm.models.protocol_server import ErrorCode, NoticeKind, PendingConfirmationMsg
from aidm.models.quests import QuestKind
from aidm.rules.finale import FinaleRefused, choose_events
from aidm.rules.quest_offers import QuestOfferRefused, answer_events
from aidm.session import combat_flow
from aidm.session.table_core import Player, TableCore
from aidm.session.table_records import PendingHostile
from aidm.session.telling import conclude

CROSS_STAY = "The party stays on this side of the border for now."
NOT_NOW = "{name} says not now; {giver} may ask again another time."
LET_GO = "{name} says not now; {giver} lets the favour go."
NOTHING = "Nobody is asking for your help right now."
SURE = "Are you sure? This ends the story."
NO_FINALE = "There is no ending to choose right now."
FIGHT_FIRST = "The fight comes first: choose the ending once it is over."


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


async def choose_finale(core: TableCore, player: Player, msg: ChooseFinale) -> None:
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero for that.")
        return
    if core.combat_active():  # M29.7c R15: the fight comes first
        core.error(player.id, ErrorCode.WRONG_PHASE, FIGHT_FIRST)
        return
    try:
        events = choose_events(core.state, msg.option_id)
    except FinaleRefused:
        core.error(player.id, ErrorCode.REFUSED, NO_FINALE)
        return
    if not msg.confirm:
        core.notice(player.id, NoticeKind.INFO, SURE)
        return
    core.apply_all(events)
    await conclude(core, None, events, actor_id=pc.id)
