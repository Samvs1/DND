"""M23.8 at the table (FakeLLM): What now? answers the asker and the screen, writes no event,
takes no turn and asks no model; the screen copy has a per-player cooldown; typed "what now" takes
the same path (also in a fight); a typed move to the locked gateway is told why it is shut."""

from pathlib import Path

from aidm.models.protocol_client import AskWhatNow, SubmitAction
from aidm.models.protocol_server import NarrationChunkMsg, WhatNowAnswer
from aidm.rules.quest_hints import FIGHTING
from tests.session.quest_offer_fixtures import fresh
from tests.session.table_fixtures import (
    fake_llm,
    join,
    of_type,
    running,
    screen_seat,
    start_fight,
)

FIRST = "Defeat the master of Gullmere Quay: Explore every corner of Gullmere Quay."


async def test_what_now_answers_the_asker_and_the_screen_without_a_turn(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    _, state, _ = fresh()
    async with running(llm, state) as (table, clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob")
        screen = await screen_seat(table)
        for seat in (ann, bob, screen):
            seat.drain()
        events, asked = len(table.log), len(fake.requests)
        ann.send(AskWhatNow())
        await table.settle()
        mine = of_type(ann.drain(), WhatNowAnswer)
        assert len(mine) == 1 and mine[0].asked_by == "Ann"
        assert mine[0].lines[0].startswith(FIRST)
        assert of_type(screen.drain(), WhatNowAnswer) == mine
        assert of_type(bob.drain(), WhatNowAnswer) == []  # only the asker's phone
        assert len(table.log) == events and len(fake.requests) == asked
        assert not table.queue and table.resolving is None
        ann.send(AskWhatNow())  # within the cooldown: the asker still gets it, the screen not
        await table.settle()
        assert len(of_type(ann.drain(), WhatNowAnswer)) == 1
        assert of_type(screen.drain(), WhatNowAnswer) == []
        clock.advance(6.0)
        ann.send(AskWhatNow())
        await table.settle()
        assert len(of_type(screen.drain(), WhatNowAnswer)) == 1


async def test_typed_what_now_takes_the_same_path(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    _, state, _ = fresh()
    async with running(llm, state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        screen = await screen_seat(table)
        ann.drain()
        screen.drain()
        events, asked = len(table.log), len(fake.requests)
        ann.send(SubmitAction(text="What should we do now?"))
        await table.settle()
        answer = of_type(ann.drain(), WhatNowAnswer)
        assert len(answer) == 1 and answer[0].lines[0].startswith(FIRST)
        assert len(of_type(screen.drain(), WhatNowAnswer)) == 1
        assert len(table.log) == events and len(fake.requests) == asked  # not declared, no turn


async def test_what_now_works_in_a_fight(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    _, state, _ = fresh()
    async with running(llm, state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        assert table.combat_active()
        ann.drain()
        events = len(table.log)
        ann.send(SubmitAction(text="what now"))
        await table.settle()
        answer = of_type(ann.drain(), WhatNowAnswer)
        assert len(answer) == 1 and answer[0].lines[0] == FIGHTING
        assert len(table.log) == events


async def test_typed_move_to_the_locked_gateway_says_why(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    _, state, _ = fresh()
    state.world.current_node = "rotting-boathouse"  # a spoke: the gateway is one of its exits
    state.world.visited.append("rotting-boathouse")
    state.world.quest_ask = None
    async with running(llm, state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.drain()
        asked = len(fake.requests)
        ann.send(SubmitAction(text="We go to the Sunken Vestry"))
        await table.settle()
        told = " ".join(m.text for m in of_type(ann.drain(), NarrationChunkMsg))
        assert "The Sunken Vestry stays shut while Gullmere Quay still hides places" in told
        assert "2 left (Saltcellar Tunnels, Heron Marsh Causeway)" in told
        assert table.state.world.current_node == "rotting-boathouse"
        assert len(fake.requests) == asked  # the engine said it, no model call
