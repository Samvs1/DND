"""The defeat epilogue (M11.1): facts only, THE guard, template fallback (FakeLLM, no network)."""

from pathlib import Path

from aidm.dm.defeat import (
    DEFEAT_STYLE,
    begin_defeat,
    defeat_event,
    defeat_facts,
    template_defeat,
)
from aidm.dm.epilogue import facts_checker
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard_flow import NarrationSource
from aidm.models.state import GameState
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import inn_state

GOOD = "Aria fell in the Lantern Inn. The common room went quiet around her."
INVENTED = "Lord Kelvane of Duskmere carried Aria away to his black tower."


def _fallen() -> GameState:
    state = inn_state()
    for cid in ("rogue", "wizard", "cleric"):
        del state.creatures[cid]
    state.creatures["fighter"].hp = 0
    return state


def test_facts_name_the_place_and_the_downed_hero() -> None:
    facts = defeat_facts(_fallen())
    assert facts.place == "Lantern Inn"
    assert facts.downed == ("Aria",) and facts.dead == () and facts.foes == ()
    template = " ".join(template_defeat(facts))
    assert "Aria lies senseless" in template and "Lantern Inn" in template
    assert not facts_checker(_fallen(), facts.lines())(template).violations


async def test_clean_defeat_text_comes_from_the_model(tmp_path: Path) -> None:
    state = _fallen()
    client, fake = fake_client(tmp_path, [fake_text(GOOD)])
    stream = begin_defeat(state, client)
    await stream.collect()
    event = defeat_event(stream, defeat_facts(state))
    assert event.text == GOOD and event.source == "model" and event.place == "Lantern Inn"
    assert fake.requests[0].messages[0]["content"] == DEFEAT_STYLE
    assert "Aria lies senseless" in str(fake.requests[0].messages[1]["content"])


async def test_invented_names_fall_back_to_the_template(tmp_path: Path) -> None:
    state = _fallen()
    client, _ = fake_client(tmp_path, [fake_text(INVENTED), fake_text(INVENTED)])
    stream = begin_defeat(state, client)
    await stream.collect()
    assert stream.source is NarrationSource.TEMPLATE
    assert "Kelvane" not in stream.text
    assert stream.text == " ".join(template_defeat(defeat_facts(state)))


async def test_no_model_still_writes_the_defeat_and_it_replays(tmp_path: Path) -> None:
    state = _fallen()
    client, fake = fake_client(tmp_path)
    client.mode = client.mode.DISABLED
    stream = begin_defeat(state, client)
    await stream.collect()
    event = defeat_event(stream, defeat_facts(state))
    assert event.source == "template" and not fake.requests
    apply(state, event)
    assert state.defeat is not None and state.defeat.text == event.text
