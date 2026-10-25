"""The CHOOSE prompt stays small (M36.5): measured with the project's token estimator for the
state before EVERY typed line (`action_declared`) in the committed playtest fixtures.

Measured at M36.5 over 1,613 lines (rounds 1-6): the messages max 1,646 tokens (p90 1,410); with
the per-menu tool schema as sent (compact JSON, the entry-id enum is most of it) max 2,488
(p90 2,150). M36.9 (colour field, longer rules, zone targets naming who stands there; paid for by
shared target notes and shorter names): messages max 1,745 (p90 1,547), total max 2,589 (p90
2,276). M36.9 iteration 2 (offer answers listed with their labels, paid for by a shorter system
text and shorter offer labels): messages max 1,763 (p90 1,555), total max 2,588 (p90 2,295). The
bounds below leave a small margin; a menu change that blows them is fixed in the
rendering (`aidm.dm.chooser_menu`), never by raising the bound.
"""

import gzip
import json
from collections.abc import Iterator

from aidm.dm.choice_tool import choice_tool
from aidm.dm.context import build_context, estimate_tokens, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.llm_types import tool_param
from aidm.models.events import LoggedEvent
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.session.reducer import apply
from tests.ai.chooser_fixtures import RECENT, REGS, TRADE
from tests.session.playtest_saves import FIXTURES

MESSAGES_BOUND = 1_800
TOTAL_BOUND = 2_600
MIN_LINES = 1_500


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
