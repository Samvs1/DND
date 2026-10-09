"""The generated player-manual sections: markers, stale detection and data coverage (M14.1)."""

import re

from aidm.data.class_defs import class_defs
from aidm.data.manual_gen import MANUAL_PATH, SECTIONS, render, splice, stale_sections
from aidm.data.race_defs import race_defs
from aidm.data.scribe_defs import scribe_table
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd


def _blank() -> str:
    return "\n".join(f"<!-- generated:{n} -->\n<!-- end generated:{n} -->" for n in SECTIONS)


def _section(text: str, name: str) -> str:
    found = re.search(
        rf"<!-- generated:{name} -->\n(.*?)\n<!-- end generated:{name} -->", text, re.DOTALL
    )
    assert found is not None
    return found.group(1)


def test_markers_round_trip_and_keep_hand_written_text() -> None:
    text = "Intro line.\n\n" + _blank() + "\n\nOutro line.\n"
    once = splice(text)
    assert once.startswith("Intro line.\n\n") and once.endswith("\n\nOutro line.\n")
    assert splice(once) == once
    assert stale_sections(once) == []


def test_blank_markers_and_a_missing_marker_are_stale() -> None:
    assert sorted(stale_sections(_blank())) == sorted(SECTIONS)
    assert stale_sections("no markers at all") == sorted(SECTIONS, key=list(SECTIONS).index)


def test_a_hand_edited_generated_block_is_stale() -> None:
    fixed = splice(_blank())
    edited = fixed.replace("| 1 | 25 gp |", "| 1 | 26 gp |", 1)
    assert stale_sections(edited) == ["scribe_prices"]
    assert render("scribe_prices") in splice(edited)


def test_the_shipped_manual_is_current() -> None:
    text = MANUAL_PATH.read_text(encoding="utf-8")
    assert stale_sections(text) == []


def test_every_class_race_and_spell_appears_in_the_manual() -> None:
    text = MANUAL_PATH.read_text(encoding="utf-8")
    for cls in class_defs().all():
        assert f"| {cls.name} |" in _section(text, "classes")
    for race in race_defs().all():
        assert f"| {race.name} |" in _section(text, "races")
    spells = _section(text, "spells")
    for spell in spell_defs().all():
        assert f"| {srd().spells.get(spell.index).name} |" in spells


def test_scribe_price_rows_match_scribe_json() -> None:
    table = scribe_table()
    prices = _section(MANUAL_PATH.read_text(encoding="utf-8"), "scribe_prices")
    for level in range(1, 6):
        assert f"| {level} | {table.base_gp + table.per_level_gp * level} gp |" in prices
    assert "| 1 | 25 gp |" in prices and "| 5 | 125 gp |" in prices  # 25 gp per level, scribe.json


def test_hand_written_numbers_match_the_rules() -> None:
    from aidm.rules.checks import DC_BY_TIER
    from aidm.rules.leveling import XP_THRESHOLDS

    text = MANUAL_PATH.read_text(encoding="utf-8")
    for dc in DC_BY_TIER.values():
        assert f"| {dc} |" in text
    for xp in XP_THRESHOLDS[1:5]:
        assert f"{xp:,}" in text or str(xp) in text
