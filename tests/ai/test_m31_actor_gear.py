"""M31.1c V21 (docs/playtests/M31_round4.md): the acting hero's gear is always in the adjudicate
context. Round 4 (quests 931-933): a sealed-door check was ruled "no crowbar at hand" while
Brienne carried one since the start; the party sheets list only worn gear, and the short sheets
used over budget drop even that."""

from aidm.dm.context import build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from tests.session.playtest_saves import logged, replay_until

_DOOR = 933  # Brienne works the crowbar into the sealed door's crust (quests 932)


def _body(budget: int) -> tuple[str, tuple[str, ...]]:
    state = replay_until("m31-r4-quests", _DOOR)
    action = logged("m31-r4-quests", _DOOR - 1).event
    text = getattr(action, "text", None)
    pack = build_context(state, ContextPurpose.ADJUDICATE, "pc-p2", text, budget_tokens=budget)
    content = str(to_messages(pack)[1]["content"])
    return content.split("## PLAYER ACTION")[0], pack.trimmed


def test_m31_actor_gear_crowbar_in_adjudicate_context() -> None:
    body, _ = _body(6000)
    line = next(x for x in body.splitlines() if "the acting hero" in x)
    assert "Brienne" in line and "Crowbar" in line and "Longsword" in line


def test_m31_actor_gear_kept_at_the_budget_limit() -> None:
    """Over budget the other heroes go to short sheets first; the actor's full sheet and the
    carried-gear line (never trimmed) stay."""
    body, trimmed = _body(800)
    assert "party" in trimmed
    assert "Crowbar" in body
    sheets = [x for x in body.splitlines() if ", HP " in x]
    brienne = next(x for x in sheets if x.lstrip("- ").startswith("Brienne"))
    assert "gear:" in brienne
    assert all("gear:" not in x for x in sheets if x is not brienne)
