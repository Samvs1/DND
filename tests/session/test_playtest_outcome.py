"""M15.1 (d): the fight's end tells its real outcome (the screen's banner and the music
stinger use it, never the party HP of a snapshot that may still be stale)."""

from pathlib import Path

from aidm.models.encounter import EncounterStatus
from aidm.models.protocol_server import CombatState
from tests.session.defeat_fixtures import end_turns_until_over, hurt, party_of
from tests.session.table_fixtures import disabled_llm, join, of_type, running, start_fight


async def test_playtest_defeat_ends_with_defeat_outcome(tmp_path: Path) -> None:
    state = party_of("fighter", hp={"fighter": 1})
    async with running(disabled_llm(tmp_path), state) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        await end_turns_until_over(table, [sam])
        ends = [m for m in of_type(sam.drain(), CombatState) if m.combat is None]
        assert ends and ends[-1].outcome is EncounterStatus.DEFEAT


async def test_playtest_won_fight_ends_with_victory_outcome(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        enc = table.state.encounter
        assert enc is not None
        foes = [cid for cid in enc.combatants if table.state.creatures[cid].pc is None]
        for foe in foes:
            await hurt(table, foe, 999)
        await end_turns_until_over(table, [ann])
        ends = [m for m in of_type(ann.drain(), CombatState) if m.combat is None]
        assert ends and ends[-1].outcome is EncounterStatus.VICTORY
