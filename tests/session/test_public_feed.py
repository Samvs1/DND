"""THE public projection of events (M7.3b): privacy scan, story history, death saves, export."""

import json
from pathlib import Path

from aidm.dm.fake_llm import FakeStep, default_fake_step, fake_tool_call
from aidm.dm.llm_backend import CompletionRequest
from aidm.dm.llm_types import LlmMode
from aidm.models.creation import CreationErrorCode
from aidm.models.dice import DieRoll, Roll
from aidm.models.events import CreatureAdded, DiceRolled, LoggedEvent
from aidm.models.protocol import AnyServerMsg
from aidm.models.protocol_client import (
    CreateCharacter,
    ExportCharacter,
    Hello,
    HostStart,
    ImportCharacter,
    SubmitAction,
)
from aidm.models.protocol_server import (
    CharacterExport,
    CreationResult,
    ErrorCode,
    ErrorMsg,
    EventMsg,
    NarrationDone,
    Notice,
    NoticeKind,
    Snapshot,
    StoryHistory,
)
from aidm.models.state import GameState
from aidm.models.world_events import NpcIntroduced
from aidm.session.lobby import PREPARED
from aidm.session.persistence import CampaignStore
from aidm.session.public_feed import MAX_ROLLS, PublicFeed, public_line
from aidm.session.reducer import apply as reduce
from aidm.session.table import Table
from tests.ai.fake_scripts import fake_client
from tests.session.table_fixtures import (
    Seat,
    drain_queue,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)
from tests.unit.rules.creation_fixtures import default_choices

HATCH = "Brine-Locked Hatch"
HATCH_TEXT = "a hatch under the nets, sealed with brine-crusted wax"


def _responder(request: CompletionRequest) -> FakeStep:
    """Default fake, but a 'hatch' action makes the DM register a HIDDEN feature."""
    names = [t["function"]["name"] for t in request.tools or []]
    last = next((m for m in reversed(request.messages) if m.get("role") == "user"), {})
    answered = any(m.get("role") == "tool" for m in request.messages)
    if "introduce_feature" in names and "hatch" in str(last.get("content", "")) and not answered:
        args = {
            "kind": "door",
            "name": HATCH,
            "description": HATCH_TEXT,
            "hidden": True,
            "discover_dc_tier": "very_hard",
        }
        return fake_tool_call("introduce_feature", args)
    return default_fake_step(request)


async def _hero(table: Table, name: str, cls: str) -> Seat:
    seat = await join(table, name)
    choices = default_choices(cls, "human", None).model_copy(update={"name": name})
    seat.send(CreateCharacter(choices=choices))
    await table.settle()
    return seat


def _private(state: GameState) -> list[str]:
    """Every motive, unrevealed secret, hidden feature and unmet boss name of the final state."""
    world = state.world
    texts = [n.motive for n in world.npcs.values() if n.motive]
    texts += [s.text for n in world.npcs.values() for s in n.secrets if not s.revealed]
    texts += [f.name for f in world.features.values() if f.hidden and not f.discovered]
    texts += [
        n.name
        for n in world.npcs.values()
        if n.role == "boss" and n.node_id != world.current_node and n.node_id not in world.visited
    ]
    return [t for t in texts if t]


async def test_privacy_scan_scripted_session_sends_no_private_text(tmp_path: Path) -> None:
    llm, fake = fake_client(tmp_path)
    fake.responder = _responder
    sent: list[AnyServerMsg] = []
    async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await _hero(table, "Ann", "fighter")
        bob = await _hero(table, "Bob", "rogue")
        ann.send(HostStart(theme="fog"))
        await table.settle()
        for text in ("I look around", "I search the nets for a hatch", "I greet everyone here"):
            ann.send(SubmitAction(text=text))
            await table.settle()
        late = table.connect()
        table.submit(late.id, Hello(name="Cy", last_seq=0))
        await table.settle()
        sent += ann.drain() + bob.drain() + drain_queue(late)
        state = table.state
    assert any(f.name == HATCH and f.hidden for f in state.world.features.values())
    assert any(n.motive for n in state.world.npcs.values()), "the sample cast has motives"
    private = [t.lower() for t in _private(state)]
    assert len(private) >= 5
    wire = [m.model_dump_json().lower() for m in sent]
    leaks = [(t, w[:80]) for t in private for w in wire if t in w]
    assert leaks == []
    assert of_type(sent, EventMsg), "public event lines were sent"
    assert all(m.line for m in of_type(sent, EventMsg))
    assert not [n for n in of_type(sent, Notice) if n.kind is NoticeKind.FALLBACK]


async def test_cast_elsewhere_is_never_named_but_present_npc_is(tmp_path: Path) -> None:
    llm, _ = fake_client(tmp_path)
    async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await _hero(table, "Ann", "fighter")
        ann.send(HostStart())
        await table.settle()
        state = table.state
        intros = [e.event for e in table.log if isinstance(e.event, NpcIntroduced)]
        here = [e for e in intros if e.npc.node_id == state.world.current_node]
        away = [e for e in intros if e.npc.node_id != state.world.current_node]
        assert away and all(public_line(state, e) is None for e in away)
        if here:
            assert (
                public_line(state, here[0]) == f"{here[0].npc.name} ({here[0].npc.role}) is here."
            )
        sent = {m.kind for m in table.public.events}
        assert "campaign_installed" not in sent and "npc_introduced" not in sent


async def test_reload_gets_story_history_and_restart_rebuilds_it(tmp_path: Path) -> None:
    llm, _ = menu_llm(tmp_path, pick(("rest:short", [], None)), pick(("look", [], None)))
    store = CampaignStore(tmp_path / "saves")
    start = GameState(campaign_id="t", seed=3)
    async with running(llm, start, store=store) as (table, _):
        ann = await _hero(table, "Ann", "fighter")
        ann.send(HostStart())
        await table.settle()
        for text in ("we take a short rest", "I look around"):
            ann.send(SubmitAction(text=text))
            await table.settle()
        fresh = table.connect()
        table.submit(fresh.id, Hello(name="Ann", token=ann.token))
        await table.settle()
        msgs = drain_queue(fresh)
        live = table.public.history()
    kinds = [m.type for m in msgs]
    assert kinds.index("story_history") == kinds.index("snapshot") + 1
    history = of_type(msgs, StoryHistory)[0]
    narrations = [e for e in history.entries if e.kind == "narration"]
    events = [e for e in history.entries if e.kind == "event"]
    assert len(narrations) >= 3 and all(e.id and e.text for e in narrations)
    assert narrations[0].tone is not None
    assert "short_rest_taken" in {e.event_kind for e in events}
    assert [e.seq for e in history.entries] == sorted(e.seq for e in history.entries)
    loaded = store.load("t")
    rebuilt = PublicFeed.rebuild(loaded.initial, loaded.log).history()
    assert [(e.kind, e.seq, e.text) for e in rebuilt.entries] == [
        (e.kind, e.seq, e.text) for e in live.entries
    ]


async def test_snapshot_shows_death_saves(tmp_path: Path) -> None:
    llm, _ = fake_client(tmp_path)
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        hero = table.state.creatures["fighter"]
        dying = hero.model_copy(
            update={"id": "pc-x", "hp": 0, "death_save_successes": 2, "death_save_failures": 1}
        )
        table.apply(CreatureAdded(creature=dying))
        ann.send(SubmitAction(text="I look around"))
        await table.settle()
        snap = of_type(ann.drain(), Snapshot)[-1]
    card = next(c for c in snap.state.party if c.id == "pc-x")
    assert card.dying and not card.stable
    assert (card.death_save_successes, card.death_save_failures) == (2, 1)


async def test_export_and_import_character_over_the_protocol(tmp_path: Path) -> None:
    llm, _ = fake_client(tmp_path)
    async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await join(table, "Ann")
        ann.send(ExportCharacter())
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.NO_CHARACTER
        choices = default_choices("wizard", "human", None).model_copy(update={"name": "Ann"})
        ann.send(CreateCharacter(choices=choices))
        await table.settle()
        ann.drain()
        ann.send(ExportCharacter())
        await table.settle()
        export = of_type(ann.drain(), CharacterExport)[0]
        assert export.name == "Ann" and json.loads(export.text)["format"] == "aidm.character"
        bob = await join(table, "Bob")
        bob.send(ImportCharacter(text="{not json"))
        doc = json.loads(export.text)
        doc["character"]["pc"]["class_index"] = "bard-of-nowhere"
        bob.send(ImportCharacter(text=json.dumps(doc)))
        bob.send(ImportCharacter(text=export.text))
        await table.settle()
        results = of_type(bob.drain(), CreationResult)
        assert [r.ok for r in results] == [False, False, True]
        assert results[0].errors[0].code is CreationErrorCode.IMPORT_INVALID
        assert results[1].errors[0].code is CreationErrorCode.UNKNOWN_CLASS
        cid = table.players[bob.player_id].creature_id
        assert cid is not None and cid == f"pc-{bob.player_id}"
        hero = table.state.creatures[cid]
        assert hero.name == "Ann" and hero.pc is not None and hero.pc.class_index == "wizard"
        ann.send(HostStart())
        await table.settle()
        bob.send(ImportCharacter(text=export.text))
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[-1].code is ErrorCode.WRONG_PHASE


async def test_fake_mode_narrates_free_text_without_the_fallback_banner(tmp_path: Path) -> None:
    for mode, prepared in ((LlmMode.FAKE, 0), (LlmMode.LIVE, 1)):
        llm, _ = fake_client(tmp_path)
        llm.mode = mode
        async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
            ann = await _hero(table, "Ann", "fighter")
            ann.send(HostStart())
            await table.settle()
            ann.send(SubmitAction(text="I wave at the gulls"))
            await table.settle()
            msgs = ann.drain()
        notices = of_type(msgs, Notice)
        fallback = [n for n in notices if n.kind is NoticeKind.FALLBACK]
        info = [n for n in notices if n.kind is NoticeKind.INFO and n.text == PREPARED]
        # The fake script has no campaign generator, so it uses the sample campaign by design;
        # a live model that fails to write a campaign says so with an INFO notice (M16.1), never
        # the sticky "lost the thread" banner: the telling itself is still live.
        assert fallback == []
        assert len(info) == prepared
        assert len(of_type(msgs, NarrationDone)) >= 2


def test_story_history_keeps_recent_dice_and_rebuild_restores_them() -> None:
    """M9.3 gap closed in M9.4: the dice panel was empty after a reconnect. The history now
    carries the recent rolls (oldest first, at most MAX_ROLLS) and a restart rebuilds them."""
    state = GameState(campaign_id="t", seed=1)
    initial = state.model_copy(deep=True)
    feed = PublicFeed()
    log: list[LoggedEvent] = []
    for n in range(MAX_ROLLS + 3):
        roll = Roll(
            expression="1d8+2",
            dice=(DieRoll(sides=8, value=1 + n % 8),),
            modifier=2,
            total=3 + n % 8,
        )
        event = DiceRolled(roll=roll, roller_id="pc-a", label=f"hit {n}")
        seq = state.event_count
        reduce(state, event)
        log.append(LoggedEvent(seq=seq, event=event))
        assert feed.add_roll(seq, event) is not None
    feed.add_roll(state.event_count, NpcIntroduced.model_construct())
    dice = feed.history().dice
    assert len(dice) == MAX_ROLLS
    assert [d.dice.label for d in dice][-1] == f"hit {MAX_ROLLS + 2}"
    assert [d.seq for d in dice] == sorted(d.seq for d in dice)
    assert dice[-1].dice.total == 3 + (MAX_ROLLS + 2) % 8 and dice[-1].dice.modifier == 2
    assert PublicFeed.rebuild(initial, log).history().dice == dice
