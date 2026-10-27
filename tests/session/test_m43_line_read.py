"""M43.1: a typed line logs how it was read (`LineRead`); the play still replays equal."""

from pathlib import Path

from aidm.models.impossible import LineRead
from tests.session.menu_play import QUESTS, menu_play
from tests.session.table_fixtures import pick

WIDOW = "widow-cabrelle"
INCENSE = "block-of-incense"


async def test_m43_typed_line_logs_the_menu_entries_it_was_read_as(tmp_path: Path) -> None:
    """quests 563 "Brienne gives Widow Cabrelle a block of incense ..." read as one give."""
    played = await menu_play(tmp_path, QUESTS, 563, pick((f"give:{INCENSE}", [WIDOW], None)))
    reads = played.of(LineRead)
    assert [r.steps for r in reads] == [(f"give:{INCENSE}>{WIDOW}",)]
    assert reads[0].creature_id == "pc-p2" and not reads[0].other and reads[0].text


async def test_m43_line_read_comes_before_the_words_are_declared(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, QUESTS, 563, pick((f"give:{INCENSE}", [WIDOW], None)))
    kinds = [type(e).__name__ for e in played.events]
    assert kinds.index("LineRead") < kinds.index("ActionDeclared")
