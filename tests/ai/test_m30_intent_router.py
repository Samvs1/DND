"""M30.0b: the one intent router. Precedence is a field of the phrase table, never row order, and
every name a row uses (resolver, condition, reading set) is known."""

import pytest

from aidm.data.intent_phrases import IntentPhrases, intent_phrases
from aidm.dm.intent_conditions import CONDITIONS
from aidm.dm.intent_match import Found, Resolver, route
from aidm.dm.intent_router import RESOLVERS
from tests.ai.tool_fixtures import party_state


def _table(first: tuple[str, int], second: tuple[str, int]) -> IntentPhrases:
    """Two rows that match the same text, in the file order given."""
    rows = [
        {
            "id": row_id,
            "scopes": ["test"],
            "family": row_id,
            "precedence": rank,
            "resolver": row_id,
            "patterns": [{"re": "{verbs} the {thing:item}", "verbs": ["open", "unbar"]}],
        }
        for row_id, rank in (first, second)
    ]
    return IntentPhrases.model_validate(
        {
            "slots": {"thing": "[a-z ]+"},
            "lexicon": {},
            "patterns": {},
            "scopes": {"test": {"base": "normal"}},
            "rows": rows,
        }
    )


def _named(name: str) -> Resolver:
    def resolve(found: Found) -> str:
        return f"{name}:{found.group('item')}"

    return resolve


_RESOLVERS = {"door_row": _named("door_row"), "gate_row": _named("gate_row")}


def _winner(table: IntentPhrases) -> object | None:
    state = party_state()
    return route(state, "pc-1", "I open the door.", _RESOLVERS, scope="test", table=table)


def test_m30_router_two_matching_rows_settled_by_precedence_not_row_order() -> None:
    assert _winner(_table(("door_row", 2), ("gate_row", 1))) == "gate_row:door"
    assert _winner(_table(("gate_row", 1), ("door_row", 2))) == "gate_row:door"
    assert _winner(_table(("door_row", 1), ("gate_row", 2))) == "door_row:door"
    assert _winner(_table(("gate_row", 2), ("door_row", 1))) == "door_row:door"


def test_m30_router_precedence_must_be_unique() -> None:
    with pytest.raises(ValueError, match="precedence must be unique"):
        _table(("door_row", 1), ("gate_row", 1))


def test_m30_router_every_row_name_is_known() -> None:
    table = intent_phrases()
    for row in table.rows:
        assert row.resolver in RESOLVERS, row.id
        assert set(row.when) <= set(CONDITIONS), row.id
    for scope in table.scopes.values():
        assert set(scope.when) <= set(CONDITIONS)
