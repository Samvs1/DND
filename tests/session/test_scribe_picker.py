"""The Scribe's line picker (M13.2): seeded, its own random, never the same line twice in a row."""

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.scribe_lines import ScribeGroup, scribe_lines
from aidm.session.scribe_picker import ScribeMemory


def _run(seed: int, group: ScribeGroup, count: int) -> list[str]:
    memory = ScribeMemory()
    lines = scribe_lines().group(group)
    return [memory.pick(lines, seed).id for _ in range(count)]


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31))
def test_no_immediate_repeat_within_a_group(seed: int) -> None:
    for group in (ScribeGroup.VICTORY_FIGHT, ScribeGroup.REFUSE_COMBAT, ScribeGroup.REVIVE):
        picks = _run(seed, group, 60)
        assert all(a != b for a, b in zip(picks, picks[1:], strict=False))


def test_every_variant_is_used_over_many_picks() -> None:
    picks = _run(7, ScribeGroup.VICTORY_FIGHT, 200)
    assert set(picks) == {line.id for line in scribe_lines().group(ScribeGroup.VICTORY_FIGHT)}


def test_a_single_line_group_repeats_its_only_line() -> None:
    assert _run(3, ScribeGroup.NONE_FALLEN, 3) == ["none_fallen.1"] * 3


def test_same_seed_same_sequence_other_seed_differs() -> None:
    assert _run(11, ScribeGroup.VICTORY_FIGHT, 30) == _run(11, ScribeGroup.VICTORY_FIGHT, 30)
    runs = {tuple(_run(seed, ScribeGroup.VICTORY_FIGHT, 30)) for seed in range(5)}
    assert len(runs) > 1


def test_groups_remember_their_own_last_line() -> None:
    memory = ScribeMemory()
    fight = scribe_lines().group(ScribeGroup.VICTORY_FIGHT)
    first = memory.pick(fight, 5)
    memory.pick(scribe_lines().group(ScribeGroup.REVIVE), 5)
    assert memory.pick(fight, 5).id != first.id
    assert memory.current is not None and memory.current.startswith("victory.fight.")
