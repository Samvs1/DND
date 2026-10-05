"""Guard lexicon data (M4.6, SPEC 6.5): loads, lowercase, the v1 vocabulary is present."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.guard_lexicon import DEFAULT_GUARD_LEXICON, guard_lexicon, load_guard_lexicon


def test_lexicon_loads_with_v1_vocabulary() -> None:
    lex = guard_lexicon()
    assert {"secret", "hidden", "concealed"} <= lex.hidden_qualifiers
    assert {"lever", "pressure plate", "trapdoor"} <= lex.feature_nouns_always
    assert "broken" in lex.destroy_words and "unbroken" not in lex.destroy_words
    assert "vial" in lex.item_synonyms["potion"]
    assert "throng" in lex.crowd_nouns and "holds only you" in lex.erase_phrases


def test_lexicon_rejects_uppercase_entries(tmp_path: Path) -> None:
    data = json.loads(DEFAULT_GUARD_LEXICON.read_text(encoding="utf-8"))
    data["titles"] = [*data["titles"], "Sister"]
    bad = tmp_path / "lexicon.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_guard_lexicon(bad)
