"""Turns the table can follow (M20.3, owner playtest 3: "it is not always clear whose turn it is").

Before, `combat_state` went out only at a hero's prompt, so after End turn the phone kept "Your
turn" until the monsters had acted AND the segment was narrated, and the board never lit a
monster. Now every AI turn sends `combat_state` (its `turn_of` names it) and a hero's prompt goes
out before the segment is told."""

from pathlib import Path

from aidm.models.commands import EndTurnCommand
from aidm.models.protocol import AnyServerMsg
from aidm.models.protocol_client import CombatCommandMsg
from aidm.models.protocol_server import CombatState, NarrationChunkMsg, TurnPrompt
from aidm.server.settings import DEFAULT_AI_TURN_PAUSE_S, server_settings_from_env
from aidm.session.table import Table
from tests.session.table_fixtures import Seat, fake_llm, join, running, start_fight


def _end_turn(table: Table, seats: list[Seat]) -> Seat:
    enc = table.state.encounter
    assert enc is not None
    active = enc.active_id() or ""
    seat = next(s for s in seats if table.players[s.player_id].creature_id == active)
    seat.send(CombatCommandMsg(command=EndTurnCommand(actor_id=active)))
    return seat


def _monster_turns(table: Table, since: int) -> list[str]:
    out: list[str] = []
    for entry in table.log[since:]:
        event = entry.event
        if event.type == "turn_started" and table.state.creatures[event.creature_id].pc is None:
            out.append(event.creature_id)
    return out


async def test_every_ai_turn_is_shown_and_the_prompt_comes_before_the_telling(
    tmp_path: Path,
) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "wolf", "wolf")
        seats = [ann, bob]
        seen: list[AnyServerMsg] = []
        for _ in range(4):  # a few hero turns: the wolves act in between
            ann.drain()
            since = len(table.log)
            _end_turn(table, seats)
            await table.settle()
            msgs = ann.drain()
            seen += msgs
            shown = [m.combat.turn_of for m in msgs if isinstance(m, CombatState) and m.combat]
            assert set(_monster_turns(table, since)) <= set(shown)
            kinds = [type(m) for m in msgs if isinstance(m, TurnPrompt | NarrationChunkMsg)]
            if TurnPrompt in kinds and NarrationChunkMsg in kinds:
                assert kinds.index(TurnPrompt) < kinds.index(NarrationChunkMsg)
            if not table.in_combat:
                break
        assert any(isinstance(m, TurnPrompt) for m in seen)


def test_ai_turn_pause_setting() -> None:
    # Owner choice (M20.3): the screen holds each monster turn; 1.5 s unless AIDM_AI_TURN_PAUSE.
    assert server_settings_from_env({}).ai_turn_pause_s == DEFAULT_AI_TURN_PAUSE_S == 1.5
    assert server_settings_from_env({"AIDM_AI_TURN_PAUSE": "0"}).ai_turn_pause_s == 0.0
    assert server_settings_from_env({"AIDM_AI_TURN_PAUSE": "99"}).ai_turn_pause_s == 5.0
    assert server_settings_from_env({"AIDM_AI_TURN_PAUSE": "soon"}).ai_turn_pause_s == 1.5
