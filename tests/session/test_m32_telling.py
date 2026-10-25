"""M32.1b X15 (related, from M32.1a's notes): with the storyteller off, an attack typed at a waiting
offer started the fight and the table then heard the stock filler "The moment passes, and the
world waits for what you do next." for the hero's turn opening, a beat where nobody acted."""

from pathlib import Path

from aidm.dm.narration_templates import QUIET_LINE
from aidm.models.encounter_events import EncounterStarted
from tests.session.m32_play import QUESTS, play
from tests.session.table_fixtures import pick


async def test_v1_m32_turn_opening_tells_no_filler(tmp_path: Path) -> None:
    shoot = pick(("attack:shortbow", ["foe:bandit"], None))  # the menu chooser's (M36.10b)
    played = await play(tmp_path, QUESTS, 162, picks=[shoot])
    assert played.of(EncounterStarted)
    told = played.told()
    assert "a fight breaks out" in told and QUIET_LINE not in told
