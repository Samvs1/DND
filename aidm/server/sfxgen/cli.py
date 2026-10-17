"""`scripts/gen_dice_sfx.py` (M26.8): build every dice sound (seeded, so a rebuild gives the same
sound), encode each ONCE to mp3 and write the timing the screen's shows follow.

Output: aidm/web/static/audio/sfx/<name>.mp3 and aidm/web/static/audio/sfx/dice_timing.json:
`{"land": s, "throw": {name: [[t, strength], ...]}, "throw_two": {name: [[[t, s], ...], [...]]},
"clack": {name: [t, ...]}, "natural_20": {"flare": s, "slam": s, "chime": s, "fade": s, "end": s}}`
(the natural 20's beats, measured from its sound: its stage show follows them). `--check`
(offline) recomputes the timing and checks every file is there. Exit codes: 0 ok, 1 check
problems.

Public API: `TIMING_FILE`, `SFX_DIR`, `timing_table`, `main`.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

from aidm.server.sfxgen.catalog import SOUNDS, Made, render
from aidm.server.sfxgen.dice import LAND_S, Impact
from aidm.server.sfxgen.synth import RATE
from aidm.server.voicegen.encode import encode_mp3

KBPS = 128
KBPS_STEREO = 192
TIMING_FILE = "dice_timing.json"
SFX_DIR = Path("aidm") / "web" / "static" / "audio" / "sfx"


type Track = list[list[float]]


def _track(impacts: tuple[Impact, ...]) -> Track:
    return [[i.at, i.strength] for i in impacts]


def timing_table(results: dict[str, Made]) -> dict[str, object]:
    """The JSON the screen reads: impact timing per throw / two-dice throw / clack variant."""
    throws: dict[str, Track] = {}
    twos: dict[str, list[Track]] = {}
    clacks: dict[str, list[float]] = {}
    beats: dict[str, float] = {}
    for sound in SOUNDS:
        made = results[sound.name]
        if sound.group == "throw":
            throws[sound.name] = _track(made.tracks[0])
        elif sound.group == "throw_two":
            twos[sound.name] = [_track(track) for track in made.tracks]
        elif sound.group == "clack":
            clacks[sound.name] = list(made.hops)
        elif sound.group == "natural_20":
            beats = dict(made.beats)
    return {
        "land": LAND_S,
        "throw": throws,
        "throw_two": twos,
        "clack": clacks,
        "natural_20": beats,
    }


def _write_json(path: Path, data: object) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str], *, root: Path, out: Callable[[str], None] = print) -> int:
    check = "--check" in argv
    target = root / SFX_DIR
    results: dict[str, Made] = {}
    for sound in SOUNDS:
        made = render(sound)
        results[sound.name] = made
        if not check:
            kbps = KBPS_STEREO if made.samples.ndim == 2 else KBPS
            encode_mp3(made.samples, RATE, kbps, target / f"{sound.name}.mp3")
            out(f"wrote {sound.name}.mp3 ({len(made.samples) / RATE:.2f} s)")
    table = timing_table(results)
    if not check:
        target.mkdir(parents=True, exist_ok=True)
        _write_json(target / TIMING_FILE, table)
        out(f"dice sfx: wrote {len(SOUNDS)} sounds and {TIMING_FILE}")
        return 0
    missing = [s.name for s in SOUNDS if not (target / f"{s.name}.mp3").is_file()]
    path = target / TIMING_FILE
    want = json.loads(json.dumps(table))
    stale = not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != want
    if missing or stale:
        what = f"missing {', '.join(missing) or 'none'}, timing {'stale' if stale else 'ok'}"
        out(f"dice sfx: STALE ({what}), run python scripts/gen_dice_sfx.py")
        return 1
    out(f"dice sfx: ok ({len(SOUNDS)} sounds)")
    return 0
