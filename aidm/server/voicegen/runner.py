"""Running the voice build: raw cache, processing, encode, index, report (M13.3).

`VoicePaths.for_root(root)` names every location: the config (data/voice/scribe.json), the raw
WAV cache and the report (gitignored artifacts/voice/raw and artifacts/voice/report) and the
output folder the game serves (aidm/web/static/audio/voice/scribe). `fetch_raw` returns the cached
raw WAV of a line (rawcache.py: one recording, or the best of `takes`; a line with `parts` has
each part fetched and spliced by parts.py); with `provider=None` (--reprocess) a missing cache
entry raises `rawcache.MissingRaw` naming the line or part, so a reprocess never calls the API.
`build_line` processes one raw WAV, encodes `<line_id>.mp3` once, writes the spectrogram and the
line report and returns the index entry.

Public API: `VoicePaths`, `LineBuild`, `raw_path`, `has_raw`, `fetch_raw`,
`reselect`, `build_line`, `build_lines`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aidm.server.voicegen.chain import process
from aidm.server.voicegen.config import VoiceConfig, VoiceLine
from aidm.server.voicegen.encode import Encoder, encode_mp3
from aidm.server.voicegen.index import (
    IndexEntry,
    file_sha256,
    load_index,
    merge_entries,
    write_index,
)
from aidm.server.voicegen.parts import assemble
from aidm.server.voicegen.provider import TtsProvider, read_wav, wav_bytes
from aidm.server.voicegen.rawcache import (
    Source,
    fetch,
    line_source,
    part_sources,
    reselect_source,
)
from aidm.server.voicegen.report import (
    LineMetrics,
    measure,
    problems,
    write_line_report,
    write_summary,
)
from aidm.server.voicegen.spectrogram import spectrogram_png


@dataclass(frozen=True)
class VoicePaths:
    config: Path
    raw_dir: Path
    report_dir: Path
    out_dir: Path

    @classmethod
    def for_root(cls, root: Path) -> VoicePaths:
        artifacts = root / "artifacts" / "voice"
        return cls(
            config=root / "data" / "voice" / "scribe.json",
            raw_dir=artifacts / "raw",
            report_dir=artifacts / "report",
            out_dir=root / "aidm" / "web" / "static" / "audio" / "voice" / "scribe",
        )


@dataclass(frozen=True)
class LineBuild:
    entry: IndexEntry
    metrics: LineMetrics
    problems: tuple[str, ...]


def raw_path(paths: VoicePaths, line: VoiceLine) -> Path:
    return paths.raw_dir / line.raw_name


def _sources(paths: VoicePaths, line: VoiceLine) -> list[Source]:
    return part_sources(paths.raw_dir, line) if line.parts else [line_source(paths.raw_dir, line)]


def has_raw(paths: VoicePaths, line: VoiceLine) -> bool:
    """Every recording the line needs is cached (one raw, or every part's raw)."""
    return all(source.path.is_file() for source in _sources(paths, line))


def fetch_raw(paths: VoicePaths, line: VoiceLine, provider: TtsProvider | None) -> bytes:
    """The line's raw WAV: its cached recording, or its parts fetched and spliced (parts.py)."""
    if not line.parts:
        return fetch(line_source(paths.raw_dir, line), provider)
    clips = [read_wav(fetch(source, provider)) for source in _sources(paths, line)]
    audio, rate = assemble(clips, line.parts)
    return wav_bytes(audio, rate, subtype="FLOAT")


def reselect(paths: VoicePaths, line: VoiceLine) -> list[tuple[str, int, float]]:
    """Re-pick each multi-take recording of the line from its cached takes: (label, take, score)."""
    picked: list[tuple[str, int, float]] = []
    for source in _sources(paths, line):
        if source.takes > 1:
            result = reselect_source(source)
            if result is not None:
                picked.append((source.label, *result))
    return picked


def build_line(paths: VoicePaths, line: VoiceLine, data: bytes, encoder: Encoder) -> LineBuild:
    raw, raw_rate = read_wav(data)
    result = process(raw, raw_rate, line.chain)
    target = paths.out_dir / f"{line.id}.mp3"
    used = encoder(result.out, result.rate, int(line.chain["output"]["bitrate_kbps"]), target)
    metrics = LineMetrics(
        **measure(line.id, line.profile, raw, raw_rate, result, line.chain), encoder=used
    )
    spectrogram_png(raw, raw_rate, result.out, result.rate, paths.report_dir / f"{line.id}.png")
    write_line_report(paths.report_dir, metrics)
    entry: IndexEntry = {
        "id": line.id,
        "text_sha": line.text_sha,
        "chain_sha": line.chain_sha,
        "file": target.name,
        "sha256": file_sha256(target),
        "duration_s": metrics.duration_s,
        "lufs": metrics.lufs,
        "true_peak_db": metrics.true_peak_db,
    }
    return LineBuild(entry=entry, metrics=metrics, problems=tuple(problems(metrics)))


def build_lines(
    paths: VoicePaths,
    config: VoiceConfig,
    lines: Sequence[VoiceLine],
    provider: TtsProvider | None,
    encoder: Encoder = encode_mp3,
) -> list[LineBuild]:
    """Fetch (or reuse) every raw first, then process; the index and report are rewritten."""
    raws = [fetch_raw(paths, line, provider) for line in lines]
    builds = [
        build_line(paths, line, data, encoder) for line, data in zip(lines, raws, strict=True)
    ]
    entries = merge_entries(config, load_index(paths.out_dir), (b.entry for b in builds))
    write_index(paths.out_dir, entries)
    write_summary(paths.report_dir, config.ids())
    return builds
