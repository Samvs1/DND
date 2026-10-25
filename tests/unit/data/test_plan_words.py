"""Plan word sets (M36.1): data/bg3/plan_words.json loads and rejects bad words."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.plan_words import load_plan_words, plan_words


def test_plan_words_load_with_come_back_words() -> None:
    words = plan_words().come_back_words
    assert {"back", "bring", "return", "fetch"} <= words


def test_plan_words_reject_uppercase(tmp_path: Path) -> None:
    bad = tmp_path / "plan_words.json"
    bad.write_text(json.dumps({"come_back_words": ["Back"]}), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_plan_words(bad)
