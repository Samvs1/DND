"""M11.2 pure pieces: the rate limit, the typing board and the public floor view."""

from aidm.models.protocol_views import PlayerInfo, QueueEntry
from aidm.session.presence import RateLimit, TypingBoard
from aidm.session.table_clock import ManualClock
from aidm.session.views import public_floor
from tests.ai.guard_fixtures import inn_state


def test_rate_limit_is_a_sliding_window_per_key() -> None:
    limit = RateLimit(limit=2, window=1.0)
    assert limit.allow("a", 0.0) and limit.allow("a", 0.5)
    assert not limit.allow("a", 0.9), "a third hit inside the window is refused"
    assert limit.allow("b", 0.9), "keys are independent"
    assert limit.allow("a", 1.0), "the first hit left the window"


def test_typing_board_generations_ignore_stale_expiry() -> None:
    clock = ManualClock()
    board = TypingBoard()
    gen1, fresh1 = board.start("p1")
    board.keep_timer("p1", clock.call_later(8, lambda: None))
    gen2, fresh2 = board.start("p1")
    assert fresh1 and not fresh2 and gen2 > gen1
    assert clock.pending() == 0, "a refresh cancels the old expiry timer"
    assert not board.expire("p1", gen1), "a stale timer does not stop a fresh start"
    assert board.ids() == ["p1"]
    assert board.expire("p1", gen2) and board.ids() == []
    board.start("p2")
    assert board.stop("p2") and not board.stop("p2")
    board.start("p3")
    board.clear()
    assert board.ids() == []


def _seats() -> list[PlayerInfo]:
    return [
        PlayerInfo(id="p1", name="Sam", creature_id="fighter"),
        PlayerInfo(id="p2", name="Mira", creature_id="rogue"),
        PlayerInfo(id="p3", name="Joe", creature_id=None),
    ]


def test_public_floor_names_holder_queue_positions_and_typing() -> None:
    state = inn_state()
    resolving = QueueEntry(player_id="p1", creature_id="fighter", text="I open the door")
    queue = [
        QueueEntry(player_id="p2", creature_id="rogue", text="I pick the lock"),
        QueueEntry(player_id="p9", creature_id="wizard", text="kicked seat"),
        QueueEntry(player_id="p3", creature_id="", text="I wave"),
    ]
    floor = public_floor(state, _seats(), queue, resolving, ["p3", "p9"])
    assert floor.holder is not None
    assert (floor.holder.name, floor.holder.hero_name) == ("Sam", "Aria")
    assert [(s.name, s.hero_name, s.position) for s in floor.queue] == [
        ("Mira", "Brannoc", 1),
        ("Joe", "", 2),
    ]
    assert [s.player_id for s in floor.typing] == ["p3"], "unknown seats are left out"


def test_public_floor_is_empty_when_nobody_acts() -> None:
    floor = public_floor(inn_state(), _seats(), [], None, [])
    assert floor.holder is None and floor.queue == () and floor.typing == ()
