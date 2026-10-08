"""The defeat flow (M11.1): party wipe -> DEFEATED, input lock, checkpoints, who may choose."""

from pathlib import Path

from aidm.models.commands import EndTurnCommand
from aidm.models.defeat import CheckpointFile, PartyDefeated
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import DeathSaveRolled
from aidm.models.leveling import LevelUpChoices
from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_client import (
    CombatCommandMsg,
    DefeatRetry,
    Give,
    HostDifficulty,
    LevelUp,
    RequestSheet,
    ShopBuy,
    SubmitAction,
    UseItem,
    Vote,
)
from aidm.models.protocol_server import (
    ErrorCode,
    ErrorMsg,
    NarrationDone,
    SheetMsg,
    Snapshot,
)
from aidm.models.protocol_views import TablePhase
from aidm.session.persistence import CHECKPOINTS, CampaignStore
from tests.session.defeat_fixtures import end_turns_until_over, hurt, party_of, travel
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


def _locked_messages(hero: str) -> list[AnyClientMsg]:
    return [
        SubmitAction(text="I stand up and keep walking"),
        CombatCommandMsg(command=EndTurnCommand(actor_id=hero)),
        Give(npc_id="npc-mira", item_id="rope"),
        ShopBuy(npc_id="npc-mira", item_id="rope", qty=1),
        Vote(vote_id="v1", ready=True),
        LevelUp(choices=LevelUpChoices()),
        UseItem(item_id="potion-of-healing"),
        HostDifficulty(monster_hp=1.0, monster_damage=1.0),
    ]


async def test_m11_logged_wolf_death_ends_in_defeat(tmp_path: Path) -> None:
    """saves/c-20261008-161136-2923: one hero, a wolf, 0 HP, defeat -> the table kept going."""
    store = CampaignStore(tmp_path / "saves")
    state = party_of("fighter", hp={"fighter": 1})
    async with running(disabled_llm(tmp_path), state, store=store) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        await end_turns_until_over(table, [sam])
        ended = [e.event for e in table.log if isinstance(e.event, EncounterEnded)]
        assert ended and ended[-1].status is EncounterStatus.DEFEAT
        assert table.phase is TablePhase.DEFEATED and not table.in_combat
        assert isinstance(table.log[-1].event, PartyDefeated)
        snap = of_type(sam.drain(), Snapshot)[-1].state
        assert snap.phase is TablePhase.DEFEATED and snap.defeat
        assert snap.checkpoint == "Lantern Inn, before the fight with Wolf"
        count = table.state.event_count
        for msg in _locked_messages("fighter"):
            sam.send(msg)
        await table.settle()
        msgs = sam.drain()
        errors = of_type(msgs, ErrorMsg)
        assert len(errors) == len(_locked_messages("fighter"))
        assert {(e.code, e.refusal) for e in errors} == {(ErrorCode.WRONG_PHASE, "defeated")}
        assert not of_type(msgs, NarrationDone), "nothing is narrated after the defeat"
        assert table.state.event_count == count
        sam.send(RequestSheet())
        await table.settle()
        assert of_type(sam.drain(), SheetMsg), "the sheet stays readable"
        assert_replays(table)


async def test_one_down_one_standing_is_no_defeat_and_death_saves_run(tmp_path: Path) -> None:
    state = party_of("fighter", "rogue", hp={"fighter": 5, "rogue": 400})
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "wolf")
        await hurt(table, "fighter", 5)
        assert table.state.creatures["fighter"].hp == 0
        assert table.phase is TablePhase.PLAY and table.in_combat
        for _ in range(12):
            await end_turns_until_over(table, [ann, bob], limit=1)
            if any(isinstance(e.event, DeathSaveRolled) for e in table.log):
                break
        assert any(isinstance(e.event, DeathSaveRolled) for e in table.log)
        assert table.phase is TablePhase.PLAY and table.state.defeat is None
        bob.send(SubmitAction(text="I hold the line"))
        await table.settle()
        assert all(e.refusal != "defeated" for e in of_type(bob.drain(), ErrorMsg))


async def test_out_of_combat_wipe_enters_defeat(tmp_path: Path) -> None:
    state = party_of("fighter")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        sam = await join(table, "Sam", "fighter")
        sam.send(SubmitAction(text="I look around"))
        await table.settle()
        await hurt(table, "fighter", table.state.creatures["fighter"].hp)
        assert table.phase is TablePhase.DEFEATED
        assert table.state.defeat is not None and "Aria" in table.state.defeat.text
        sam.send(SubmitAction(text="I crawl to the bar"))
        await table.settle()
        assert of_type(sam.drain(), ErrorMsg)[-1].refusal == "defeated"
        assert_replays(table)


async def test_downed_hero_cannot_type_while_an_ally_stands(tmp_path: Path) -> None:
    state = party_of("fighter", "rogue")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await join(table, "Bob", "rogue")
        await hurt(table, "fighter", table.state.creatures["fighter"].hp)
        assert table.phase is TablePhase.PLAY
        ann.send(SubmitAction(text="I get up"))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[-1].code is ErrorCode.NO_CHARACTER


async def test_checkpoints_at_arrival_and_fight_start(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), party_of("fighter"), store=store) as (table, _):
        await join(table, "Sam", "fighter")
        await travel(table, "forest")
        arrival = table.state.event_count
        await start_fight(table, "wolf")
        marks = table.checkpoints.checkpoints
        assert [(m.kind, m.label) for m in marks] == [
            ("arrival", "Whisperwood, on arrival"),
            ("fight", "Whisperwood, before the fight with Wolf"),
        ]
        assert marks[0].seq == arrival and marks[1].seq > arrival
        folder = store.folder(table.state.campaign_id)
        saved = CheckpointFile.model_validate_json((folder / CHECKPOINTS).read_text("utf-8"))
        assert saved.checkpoints == marks and saved.retries == 0


async def test_only_the_host_or_sole_player_chooses(tmp_path: Path) -> None:
    state = party_of("fighter", "rogue")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        host = await join(table, "Ann", "fighter")
        guest = await join(table, "Bob", "rogue")
        guest.send(DefeatRetry())
        await table.settle()
        assert of_type(guest.drain(), ErrorMsg)[-1].refusal == "not_defeated"
        await hurt(table, "rogue", 999)
        await hurt(table, "fighter", 999)
        assert table.phase is TablePhase.DEFEATED
        guest.send(DefeatRetry())
        await table.settle()
        refused = of_type(guest.drain(), ErrorMsg)[-1]
        assert refused.code is ErrorCode.NOT_HOST and refused.refusal == "defeat_host_only"
        assert table.phase is TablePhase.DEFEATED
        host.send(DefeatRetry())
        await table.settle()
        assert of_type(host.drain(), ErrorMsg)[-1].refusal == "no_checkpoint"
