"""Vendored SRD files exist, parse as JSON lists and have sane sizes.

Counts come from the pinned 5e-database commit (see data/srd/SOURCE.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SRD_DIR = Path(__file__).resolve().parents[3] / "data" / "srd"

EXPECTED_FILES = [
    "ability_scores",
    "alignments",
    "backgrounds",
    "classes",
    "conditions",
    "damage_types",
    "equipment",
    "equipment_categories",
    "feats",
    "features",
    "languages",
    "levels",
    "magic_items",
    "magic_schools",
    "monsters",
    "proficiencies",
    "races",
    "rule_sections",
    "rules",
    "skills",
    "spells",
    "subclasses",
    "subraces",
    "traits",
    "weapon_properties",
]

# Real counts at the pinned SHA: spells 319, monsters 334, equipment 237.
MIN_COUNTS = {"spells": 300, "monsters": 300, "equipment": 200}


def load(name: str) -> list[object]:
    data = json.loads((SRD_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_srd_file_exists_and_is_nonempty_list(name: str) -> None:
    assert (SRD_DIR / f"{name}.json").is_file()
    assert len(load(name)) > 0


@pytest.mark.parametrize(("name", "minimum"), sorted(MIN_COUNTS.items()))
def test_srd_minimum_counts(name: str, minimum: int) -> None:
    assert len(load(name)) >= minimum


def test_srd_source_note_present() -> None:
    text = (SRD_DIR / "SOURCE.md").read_text(encoding="utf-8")
    assert "a6212beb4b278917c2cff41c2b04c4ef4f3e0d6f" in text
