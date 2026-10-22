"""M27.11 review fix 3: a spell with no attack or save (Sleep) gets one public line, built from the
cast and the conditions it applied, so the strip and THIS ROUND are not silent."""

from aidm.models.combat_events import SpellCast
from aidm.models.commands import UseItemCommand
from aidm.models.encounter import Side
from aidm.models.events import LoggedEvent
from aidm.models.protocol_server import EventMsg
from aidm.session.public_feed import PublicFeed
from aidm.session.spell_line import rollless
from tests.unit.rules.combat_fixtures import ScriptedRng, do, fight, monster
from tests.unit.rules.item_fixtures import CAVE, gear_fight, hero
from tests.unit.rules.spell_fixtures import cast, caster


def _lines(feed: PublicFeed) -> list[str]:
    return [m.line for m in feed.events if m.kind == "spell_cast"]


def test_rollless_spells_are_told_from_their_effects() -> None:
    assert rollless("sleep") and not rollless("fire-bolt") and not rollless("burning-hands")


def test_a_sleep_scroll_reads_as_one_line_with_the_sleepers() -> None:
    state = gear_fight(
        CAVE,
        hero(gear=["scroll-of-sleep"]),
        (monster("gob", hp=5), Side.HOSTILE, "b"),
        (monster("gob2", hp=6), Side.HOSTILE, "b"),
    )
    initial = state.model_copy(deep=True)
    cmd = UseItemCommand(actor_id="hero", item="scroll-of-sleep", target_zone="b")
    events = do(state, cmd, ScriptedRng(8, 8, 8, 8, 8))
    log = [LoggedEvent(seq=i, event=e) for i, e in enumerate(events)]
    feed = PublicFeed.rebuild(initial, log)
    names = [state.creatures[c].name for c in ("gob", "gob2")]
    assert _lines(feed) == [
        f"{state.creatures['hero'].name} reads Sleep: {', '.join(names)} asleep"
    ]
    cast_seq = next(i for i, e in enumerate(events) if isinstance(e, SpellCast))
    assert [m.seq for m in feed.events if m.kind == "spell_cast"] == [cast_seq]


def test_a_sleep_from_a_slot_casts_and_a_live_feed_sends_it_once() -> None:
    me = caster("wiz", "wizard", spells=["sleep"], slots={1: 2})
    state = fight(
        [
            (me, Side.PARTY, "gate"),
            (monster("g1", ac=13, hp=5), Side.HOSTILE, "gate"),
        ]
    )
    feed = PublicFeed()
    sent: list[EventMsg] = []
    events = cast(state, "wiz", "sleep", ScriptedRng(8, 8, 8, 8, 8), zone="gate", slot=1)
    for seq, event in enumerate(events):
        done = feed.spell_before(state, event)
        if done is not None:
            sent.append(done)
        feed.spell_after(state, seq, event)
    last = feed.spell_flush(state)  # the job ended with the cast
    if last is not None:
        sent.append(last)
    assert [m.line for m in sent] == [f"{me.name} casts Sleep: {state.creatures['g1'].name} asleep"]
