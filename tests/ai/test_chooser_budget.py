"""The CHOOSE prompt stays small (M36.5): measured with the project's token estimator for the
state before EVERY typed line (`action_declared`) in the committed playtest fixtures.

Measured at M36.5 over 1,613 lines (rounds 1-6): the messages max 1,646 tokens (p90 1,410); with
the per-menu tool schema as sent (compact JSON, the entry-id enum is most of it) max 2,488
(p90 2,150). M36.9 (colour field, longer rules, zone targets naming who stands there; paid for by
shared target notes and shorter names): messages max 1,745 (p90 1,547), total max 2,589 (p90
2,276). M36.9 iteration 2 (offer answers listed with their labels, paid for by a shorter system
text and shorter offer labels): messages max 1,763 (p90 1,555), total max 2,588 (p90 2,295).
M38.2 (attack-roll spells at a person): messages max 1,791, total 2,586. M38.4 (rule 1 names the
off target, NOT OFFERED targets, harmful spells at a person, labels that say what they do; paid
by writing a target note once): measured with the not-offered targets the chooser adds, messages
max 1,789 (p90 1,580), total max 2,594 (p90 2,304). M38.5 fix (rule 1 narrowed, people not
here no longer NOT OFFERED, `strike:` entries, the demand label): messages max 1,792 (p90
1,591), total max 2,587 (p90 2,315). M40.1: a confirm card waiting for the hero adds its two
entries (session state, not in the log): measured on the corpus rows that name their card
(`card`), +42 message tokens on the two round-7 rows. M40.4 (the m39-r7 fixtures of M40.3 put
a cleric's full turn at 1,868): a spent entry drops its targets and a repeated long target list
is "as for <entry>": over 1,994 lines messages max 1,782 (p90 1,587), total max 2,587 (p90
2,300). The bounds below leave a small margin; a
menu change that blows them is fixed in the rendering (`aidm.dm.chooser_menu`), never by raising
the bound.
"""

import gzip
import json
from collections.abc import Iterator

from aidm.dm.choice_tool import choice_tool
from aidm.dm.context import build_context, estimate_tokens, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.llm_types import tool_param
from aidm.models.action_menu import ActionMenu
from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_unoffered import with_unoffered
from aidm.session.reducer import apply
from scripts.interpret.corpus import load_corpus
from scripts.interpret.evaluate import row_menu
from tests.ai.chooser_fixtures import RECENT, REGS, TRADE, recent_at, state_at
from tests.session.playtest_saves import FIXTURES

MESSAGES_BOUND = 1_800
TOTAL_BOUND = 2_600
MIN_LINES = 1_500
CORPUS = FIXTURES.parent / "interpret" / "corpus.jsonl"


def _typed_lines() -> Iterator[tuple[str, int, int, int]]:
    """(run, seq, message tokens, tool schema tokens) for every typed line, replayed once."""
    for folder in sorted(FIXTURES.iterdir()):
        if not (folder / "initial.json").exists():
            continue
        state = GameState.model_validate_json((folder / "initial.json").read_text("utf-8"))
        with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as raw:
            log = [LoggedEvent.model_validate_json(line) for line in raw if line.strip()]
        for i, entry in enumerate(log):
            event = entry.event
            if isinstance(event, ActionDeclared):
                menu = build_menu(state, event.creature_id, REGS, TRADE)
                menu = with_unoffered(state, menu, event.text)  # M38.4: as the chooser sends it
                recent = [e.event for e in log[max(0, i - RECENT) : i]]
                pack = build_context(
                    state,
                    ContextPurpose.CHOOSE,
                    event.creature_id,
                    event.text,
                    events=recent,
                    menu=menu,
                )
                words = sum(estimate_tokens(m["content"]) for m in to_messages(pack))
                schema = json.dumps(tool_param(choice_tool(menu)), separators=(",", ":"))
                yield folder.name, entry.seq, words, estimate_tokens(schema)
            apply(state, event)


def test_choose_prompt_fits_the_budget_on_every_fixture_line() -> None:
    rows = list(_typed_lines())
    assert len(rows) >= MIN_LINES
    worst_words = max(rows, key=lambda r: r[2])
    worst_total = max(rows, key=lambda r: r[2] + r[3])
    assert worst_words[2] <= MESSAGES_BOUND, worst_words
    assert worst_total[2] + worst_total[3] <= TOTAL_BOUND, worst_total


def _tokens(
    state: GameState, actor_id: str, text: str, recent: list[AnyEvent], menu: ActionMenu
) -> tuple[int, int]:
    """(message tokens, tool schema tokens) as the chooser sends them."""
    pack = build_context(state, ContextPurpose.CHOOSE, actor_id, text, events=recent, menu=menu)
    words = sum(estimate_tokens(m["content"]) for m in to_messages(pack))
    schema = json.dumps(tool_param(choice_tool(menu)), separators=(",", ":"))
    return words, estimate_tokens(schema)


def test_choose_prompt_with_a_waiting_card_fits_the_budget() -> None:
    """M40.1: the lines typed while a confirm card waited, with the card's entries."""
    rows = [r for r in load_corpus(CORPUS) if r.card]
    assert rows
    for row in rows:
        state = state_at(row.run, row.seq)
        menu = with_unoffered(state, row_menu(state, row), row.text)
        assert any(e.id == "card:yes" for e in menu.entries)
        recent = recent_at(row.run, row.seq)
        words, schema = _tokens(state, row.actor_id, row.text, recent, menu)
        assert words <= MESSAGES_BOUND and words + schema <= TOTAL_BOUND, row.id
