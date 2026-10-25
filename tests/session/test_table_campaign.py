"""Table actor over a campaign: arrival offers, offer fights, loot, epilogue (M6.2)."""

import random
from pathlib import Path

from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import EndTurnCommand
from aidm.models.encounter_events import EncounterEnded
from aidm.models.protocol_client import AnswerOffer, CombatCommandMsg, SubmitAction
from aidm.models.protocol_server import (
    EncounterOfferMsg,
    EpilogueMsg,
    ErrorCode,
    ErrorMsg,
    LevelUpAvailable,
    NarrationDone,
)
from aidm.models.protocol_views import TablePhase
from aidm.models.world_events import LevelUpReady, NodeDescribed, PartyMoved
from aidm.session.combat_runner import ai_command
from tests.ai.epilogue_fixtures import finished_campaign
from tests.session.progression_fixtures import campaign_state, plan
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)

R1 = plan().acts[0].region


async def _drive_fight(seat: Seat) -> None:
    table, rng = seat.table, random.Random(2)
    for _ in range(300):
        enc = table.state.encounter
        if not table.in_combat or enc is None:
            return
        active = enc.active_id()
        assert active is not None and active == table.players[seat.player_id].creature_id
        command = ai_command(table.state, active, table.regs.combat, rng)
        seat.send(CombatCommandMsg(command=command or EndTurnCommand(actor_id=active)))
        await table.settle()


async def test_arrival_offer_fight_loot_and_back_to_exploration(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    spoke = R1.spokes[0]
    travel = pick(("travel", [spoke.id], None))  # M36.10a; the AI is otherwise down
    llm = menu_llm(tmp_path, travel, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(AnswerOffer(choice=OfferChoice.FIGHT))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.REFUSED
        ann.send(SubmitAction(text=f"travel to {spoke.name}"))
        await table.settle()
        assert table.state.world.current_node == spoke.id
        msgs = ann.drain()
        offers = of_type(msgs, EncounterOfferMsg)
        assert offers and offers[0].offer.node_id == spoke.id and offers[0].offer.foes
        kinds = [type(e.event) for e in table.log]
        assert kinds.index(PartyMoved) < kinds.index(NodeDescribed)
        ann.send(AnswerOffer(choice=OfferChoice.FIGHT))
        await table.settle()
        assert table.in_combat or any(isinstance(e.event, EncounterEnded) for e in table.log)
        await _drive_fight(ann)
        assert not table.in_combat
        assert any(isinstance(e.event, EncounterEnded) for e in table.log)
        ready = [e.event for e in table.log if isinstance(e.event, LevelUpReady)]
        level_msgs = of_type(ann.drain(), LevelUpAvailable)
        mine = [r for r in ready if r.creature_id == "fighter"]
        assert len(level_msgs) == len(mine)
        assert_replays(table)


async def test_completed_campaign_writes_the_epilogue_once(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign()
    toast = pick(other="")  # the storyteller's line (M36.10a); the AI is otherwise down
    llm = menu_llm(tmp_path, toast, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="We raise a toast to the fallen"))
        await table.settle()
        msgs = ann.drain()
        epilogue = of_type(msgs, EpilogueMsg)
        assert len(epilogue) == 1 and epilogue[0].text.strip()
        assert of_type(msgs, NarrationDone)
        assert table.state.campaign is not None and table.state.campaign.epilogue
        assert table.phase is TablePhase.ENDED
        ann.send(SubmitAction(text="And another toast"))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.WRONG_PHASE
        assert_replays(table)
