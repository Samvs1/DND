"""Schema and SRD cross-reference tests for data/bg3/backgrounds.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.background_defs import BackgroundDef, background_defs, load_background_defs
from aidm.data.srd import srd

GOOD = {
    "index": "x",
    "name": "X",
    "skills": ["insight", "religion"],
    "gear": [{"item": "pouch", "qty": 1}],
    "flavour": "A line.",
}


def test_between_six_and_eight_backgrounds() -> None:
    assert 6 <= len(background_defs()) <= 8
    assert "acolyte" in background_defs()


def test_references_exist_in_srd() -> None:
    for bg in background_defs().all():
        assert all(s in srd().skills for s in bg.skills), bg.index
        assert all(t in srd().proficiencies for t in bg.tools), bg.index
        assert all(g.item in srd().equipment for g in bg.gear), bg.index


def test_golden_acolyte_skills_match_srd() -> None:
    # SRD 5.1 Acolyte: skill proficiencies Insight and Religion.
    srd_bg = srd().backgrounds.get("acolyte")
    srd_skills = {p.index.removeprefix("skill-") for p in srd_bg.starting_proficiencies}
    assert set(background_defs().get("acolyte").skills) == srd_skills == {"insight", "religion"}


def test_flavour_lines_are_single_sentences() -> None:
    for bg in background_defs().all():
        assert bg.flavour.endswith(".") and "\n" not in bg.flavour


def test_schema_rejects_bad_entries() -> None:
    assert BackgroundDef.model_validate(GOOD).tools == ()
    for patch in ({"skills": ["insight", "insight"]}, {"nope": 1}, {"gear": []}, {"skills": ["a"]}):
        with pytest.raises(ValidationError):
            BackgroundDef.model_validate({**GOOD, **patch})


def test_loader_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "bg.json"
    path.write_text(json.dumps([GOOD, GOOD]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_background_defs(path)
