"""Every dice sound the game ships (M26.8): name, recipe, seed and loudness. The names are the
`sfx.<name>` manifest keys (`aidm.server.sfxgen.names.DICE_SFX`) and the files
`aidm/web/static/audio/sfx/<name>.mp3`. Variants share a prefix (`dice_throw_1`..`_6`); the screen
never plays the same one twice in a row (js/audio/sfx.js). Success and a natural 20 are single
files on a real CC0 recording (payoff.py); the natural 20 carries the beats its stage show follows.

Public API: `Made`, `Sound`, `SOUNDS`, `render`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from aidm.server.sfxgen import payoff, stings
from aidm.server.sfxgen.dice import Impact, clack, throw
from aidm.server.sfxgen.synth import Audio, finish


@dataclass(frozen=True)
class Made:
    samples: Audio
    tracks: tuple[tuple[Impact, ...], ...] = ()  # a throw: the impacts of each die
    hops: tuple[float, ...] = ()  # a clack: the landing and its little hops
    beats: tuple[tuple[str, float], ...] = ()  # the natural 20: the moments its show lands on


@dataclass(frozen=True)
class Sound:
    name: str
    make: Callable[[], Made]
    rms_db: float | None  # None: the recipe sets its own level (the stereo natural 20)
    group: str  # "throw", "throw_two", "clack" carry impact timing, "natural_20" its beats; "" none


def _plain(fn: Callable[[], Audio]) -> Callable[[], Made]:
    return lambda: Made(fn())


def _throw(seed: int, dice: int) -> Made:
    samples, tracks = throw(seed, dice)
    return Made(samples, tracks=tuple(tuple(t) for t in tracks))


def _clack(seed: int) -> Made:
    samples, hops = clack(seed)
    return Made(samples, hops=tuple(hops))


def _natural_20() -> Made:
    samples = payoff.natural_20()
    return Made(samples, beats=tuple(payoff.natural_20_beats(samples).items()))


def _sounds() -> tuple[Sound, ...]:
    out: list[Sound] = []
    for i in range(6):
        out.append(Sound(f"dice_throw_{i + 1}", lambda s=100 + i: _throw(s, 1), -20.0, "throw"))
    for i in range(3):
        out.append(
            Sound(f"dice_throw_two_{i + 1}", lambda s=200 + i: _throw(s, 2), -19.0, "throw_two")
        )
    for i in range(4):
        out.append(Sound(f"dice_clack_{i + 1}", lambda s=300 + i: _clack(s), -24.0, "clack"))
    out.append(Sound("roll_success", _plain(payoff.success), -20.0, ""))
    for i in range(2):
        out.append(
            Sound(f"roll_failure_{i + 1}", _plain(lambda s=410 + i: stings.failure(s)), -22.0, "")
        )
    out.append(Sound("roll_natural_20", _natural_20, None, "natural_20"))
    out.append(Sound("roll_natural_1", _plain(lambda: stings.natural_1(425)), -21.0, ""))
    out.append(Sound("hit", _plain(lambda: stings.hit(430)), -22.0, ""))
    out.append(Sound("hit_2", _plain(lambda: stings.hit(431)), -22.0, ""))
    out.append(Sound("miss", _plain(lambda: stings.miss(440)), -28.0, ""))
    out.append(Sound("miss_2", _plain(lambda: stings.miss(441)), -28.0, ""))
    out.append(Sound("crit", _plain(lambda: stings.hit(450, crit=True)), -21.0, ""))
    return tuple(out)


SOUNDS = _sounds()


def render(sound: Sound) -> Made:
    """The finished sound (loudness set, tail trimmed) with its impact timing."""
    made = sound.make()
    if sound.rms_db is None:
        return made
    return Made(finish(made.samples, rms_db=sound.rms_db), made.tracks, made.hops, made.beats)
