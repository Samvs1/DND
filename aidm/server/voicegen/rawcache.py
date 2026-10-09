"""The raw WAV cache of the voice build: one source per cached recording (M13.4d-f).

A `Source` is one thing Fish records: a whole line (`<line_id>__<key>.wav`) or one part of a line
(`part__<key>.wav`, shared by every line with the same part). `fetch` returns the cached raw or
asks the provider once, or `takes` times keeping the best by the source's chooser (every take is
kept as `<raw>.take<i>.wav` with a `<raw>.takes.json` summary); without a provider (--reprocess)
a missing raw raises `MissingRaw`. `reselect` re-picks from the cached takes with no API call.

Choosers: "final_word" (takes.best_take: the last word after a pause stands alone, long, level or
falling) and "phrase" (takes.best_phrase: drawn out, near the line's pitch, closing like a
statement).

Public API: `Source`, `MissingRaw`, `line_source`, `part_sources`, `fetch`, `reselect_source`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from aidm.server.voicegen.config import VoiceLine
from aidm.server.voicegen.provider import TtsProvider, read_wav
from aidm.server.voicegen.takes import best_phrase, best_take, phrase_score, take_score

type Audio = npt.NDArray[np.float64]
type Rows = list[dict[str, float]]
type Chooser = Callable[[list[tuple[Audio, int]]], tuple[int, Rows]]


class MissingRaw(LookupError):
    """--reprocess found no cached raw WAV for a line or part."""


def _final_word(takes: list[tuple[Audio, int]]) -> tuple[int, Rows]:
    chosen, words = best_take(takes)
    return chosen, [{**w.as_dict(), "score": take_score(w)} for w in words]


def _phrase(ref_f0_hz: float) -> Chooser:
    def choose(takes: list[tuple[Audio, int]]) -> tuple[int, Rows]:
        chosen, phrases = best_phrase(takes, ref_f0_hz)
        return chosen, [{**p.as_dict(), "score": phrase_score(p)} for p in phrases]

    return choose


@dataclass(frozen=True)
class Source:
    label: str
    text: str
    voice: dict[str, Any]
    takes: int
    path: Path
    chooser: Chooser


def line_source(raw_dir: Path, line: VoiceLine) -> Source:
    return Source(line.id, line.text, line.voice, line.takes, raw_dir / line.raw_name, _final_word)


def part_sources(raw_dir: Path, line: VoiceLine) -> list[Source]:
    out: list[Source] = []
    for number, part in enumerate(line.parts):
        chooser = _phrase(part.ref_f0_hz) if part.select == "phrase" else _final_word
        label = f"{line.id}#{number}"
        out.append(
            Source(label, part.text, part.voice, part.takes, raw_dir / part.raw_name, chooser)
        )
    return out


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _choose(source: Source, takes: list[bytes]) -> tuple[int, float]:
    chosen, rows = source.chooser([read_wav(data) for data in takes])
    summary = {"line": source.label, "chosen": chosen, "takes": rows}
    stem = source.path.stem
    _atomic_bytes(
        source.path.with_name(f"{stem}.takes.json"), json.dumps(summary, indent=2).encode()
    )
    _atomic_bytes(source.path, takes[chosen])
    return chosen, float(rows[chosen]["score"])


def fetch(source: Source, provider: TtsProvider | None) -> bytes:
    if source.path.is_file():
        return source.path.read_bytes()
    if provider is None:
        raise MissingRaw(f"{source.label}: no cached raw WAV ({source.path.name}); run with --yes")
    if source.takes <= 1:
        data = provider.synthesize(source.text, source.voice)
        _atomic_bytes(source.path, data)
        return data
    takes = [provider.synthesize(source.text, source.voice) for _ in range(source.takes)]
    for number, data in enumerate(takes):
        _atomic_bytes(source.path.with_name(f"{source.path.stem}.take{number}.wav"), data)
    return takes[_choose(source, takes)[0]]


def reselect_source(source: Source) -> tuple[int, float] | None:
    """Re-pick the best cached take (no API call): (chosen index, its score), or None."""
    stem = source.path.stem
    files = sorted(
        source.path.parent.glob(f"{stem}.take*.wav"), key=lambda f: int(f.stem.rsplit("take", 1)[1])
    )
    if not files:
        return None
    return _choose(source, [f.read_bytes() for f in files])
