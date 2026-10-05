"""Check wording in event lines and template narration (M7.3b): articles and capitalised names."""

import pytest

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.dm.wording import skill_name, with_article
from aidm.models.abilities import Skill
from aidm.models.checks import CheckKind
from aidm.models.events import CheckResolved
from tests.ai.tool_fixtures import party_state, run_tool


def _check(what: str) -> CheckResolved:
    result = run_tool(
        party_state(),
        "request_check",
        actor="fighter",
        ability_or_skill=what,
        dc_tier="easy",
        reason="try",
    )
    events = result.events
    return next(e for e in events if isinstance(e, CheckResolved))


@pytest.mark.parametrize(
    ("what", "phrase"),
    [
        ("investigation", "an Investigation check"),
        ("athletics", "an Athletics check"),
        ("stealth", "a Stealth check"),
        ("sleight-of-hand", "a Sleight of Hand check"),
        ("animal-handling", "an Animal Handling check"),
        ("int", "an Intelligence check"),
        ("str", "a Strength check"),
    ],
)
def test_check_lines_use_the_right_article_and_names(what: str, phrase: str) -> None:
    line = event_line(party_state(), _check(what))
    assert line is not None and phrase in line
    assert " a investigation" not in line.lower() and " a int" not in line.lower()


def test_template_check_lines_use_full_names() -> None:
    line = template_line(party_state(), _check("str"))
    assert line is not None and "Strength attempt" in line
    dex = _check("dex")
    save = dex.model_copy(update={"result": dex.result.model_copy(update={"kind": CheckKind.SAVE})})
    saved = template_line(party_state(), save)
    assert saved is not None and "Dexterity save" in saved


def test_with_article_and_skill_names() -> None:
    assert with_article("Insight check") == "an Insight check"
    assert with_article("Perception check") == "a Perception check"
    assert skill_name(Skill.SLEIGHT_OF_HAND) == "Sleight of Hand"
