"""The dice sounds (M26.8): the names the game ships, repeatable seeds, the impact timing the screen
bounces the dice on, safe levels, and the good news built on one CC0 recording with the natural 20's
beats measured from its own sound."""

import numpy as np

from aidm.server.asset_keys import SFX_NAMES
from aidm.server.sfxgen.catalog import SOUNDS, render
from aidm.server.sfxgen.cli import timing_table
from aidm.server.sfxgen.dice import LAND_S, clack, throw
from aidm.server.sfxgen.impact import SOURCE
from aidm.server.sfxgen.names import DICE_SFX
from aidm.server.sfxgen.synth import RATE


def test_the_catalog_builds_exactly_the_shipped_names() -> None:
    assert tuple(s.name for s in SOUNDS) == DICE_SFX
    assert set(DICE_SFX) <= set(SFX_NAMES)


def test_a_seed_always_gives_the_same_throw() -> None:
    a, ta = throw(101)
    b, tb = throw(101)
    c, _ = throw(102)
    assert np.array_equal(a, b) and ta == tb
    assert not np.array_equal(a, c)


def test_a_throw_hits_the_table_first_and_settles_at_the_landing() -> None:
    for seed in range(100, 106):
        _, tracks = throw(seed)
        track = tracks[0]
        assert 0.19 <= track[0].at <= 0.27
        assert abs(track[-1].at - LAND_S) < 1e-3
        gaps = [b.at - a.at for a, b in zip(track, track[1:], strict=False)]
        assert all(g > 0 for g in gaps) and gaps == sorted(gaps, reverse=True)  # bounces shrink
        assert track[0].strength > track[1].strength


def test_two_dice_land_a_moment_apart() -> None:
    _, tracks = throw(200, dice=2)
    assert len(tracks) == 2
    assert tracks[0][-1].at != tracks[1][-1].at


def test_a_clack_starts_at_once() -> None:
    _, hops = clack(300)
    assert hops[0] == 0.0 and hops == sorted(hops) and hops[-1] < 0.2


def test_every_sound_is_short_and_never_clips() -> None:
    for sound in SOUNDS:
        made = render(sound)
        # the natural 20's room tail rings on under the next line for a moment (under 4 s)
        assert 0.25 < len(made.samples) / RATE < 4.0, sound.name
        assert np.max(np.abs(made.samples)) <= 10 ** (-1 / 20) + 1e-9, sound.name


def test_the_timing_table_has_every_throw_and_clack() -> None:
    table = timing_table({s.name: render(s) for s in SOUNDS})
    assert table["land"] == LAND_S
    throws, twos, clacks = table["throw"], table["throw_two"], table["clack"]
    assert isinstance(throws, dict) and isinstance(twos, dict) and isinstance(clacks, dict)
    assert len(throws) == 6 and len(twos) == 3 and len(clacks) == 4
    beats = table["natural_20"]
    assert isinstance(beats, dict) and set(beats) == {"flare", "slam", "chime", "fade", "end"}


def _bands(samples: np.ndarray) -> tuple[float, float, float]:
    """Spectral centroid (Hz), the energy share below 250 Hz and the share above 3 kHz."""
    power = np.abs(np.fft.rfft(samples)) ** 2
    freq = np.fft.rfftfreq(len(samples), 1 / RATE)
    total = float(np.sum(power))
    centroid = float(np.sum(freq * power)) / total
    return (
        centroid,
        float(np.sum(power[freq < 250])) / total,
        float(np.sum(power[freq > 3000])) / total,
    )


def test_a_throw_sounds_like_wood_not_metal() -> None:
    """Owner tuning 2026-10-16: a meaty low thud and a wooden knock, never high or metallic.
    Before the tuning the throws sat near 2.5 kHz with up to 42 percent above 3 kHz."""
    for sound in SOUNDS:
        if sound.group not in ("throw", "throw_two", "clack"):
            continue
        centroid, low, top = _bands(render(sound).samples)
        assert centroid < 900, (sound.name, centroid)
        assert low > 0.25, (sound.name, low)
        assert top < 0.05, (sound.name, top)


def _sound(name: str) -> np.ndarray:
    return render(next(s for s in SOUNDS if s.name == name)).samples


def test_success_is_one_sound_that_never_varies() -> None:
    """Owner rule 2026-10-17: a sound the owner approved plays exactly, every time (a lowered
    second version read as "the sound changed")."""
    assert "roll_success" in DICE_SFX
    assert not [n for n in DICE_SFX if n.startswith("roll_success_")]
    assert np.array_equal(_sound("roll_success"), _sound("roll_success"))


def test_the_good_news_is_built_on_the_cc0_recording() -> None:
    sources = (SOURCE.parent / "SOURCES.md").read_text(encoding="utf-8")
    assert SOURCE.is_file() and SOURCE.name in sources
    assert "CC0" in sources and "freesound.org/s/570855" in sources and "rafaelzimrp" in sources


def test_the_natural_20_is_one_stereo_sound_of_three_seconds() -> None:
    samples = _sound("roll_natural_20")
    assert samples.ndim == 2 and samples.shape[1] == 2
    assert abs(len(samples) / RATE - 3.0) < 0.01
    left, right = samples[:, 0], samples[:, 1]
    assert float(np.corrcoef(left, right)[0, 1]) < 0.98  # the sparkle differs per ear (width)


def test_the_natural_20_beats_are_measured_from_its_sound() -> None:
    """The stage show lands on these (prototype v17, owner: "they look perfect now"): the ignite
    hit at 0.21 s, the slam at ~1.315 s, the recording's own ring at 1.79 s, the fade at 2.7 s."""
    table = timing_table({s.name: render(s) for s in SOUNDS})
    beats = table["natural_20"]
    assert isinstance(beats, dict)
    want = {"flare": 0.21, "slam": 1.315, "chime": 1.79, "fade": 2.7, "end": 3.0}
    for name, at in want.items():
        assert abs(float(beats[name]) - at) <= 0.015, (name, beats[name])
