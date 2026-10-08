"""Running the voice build: raw cache, processing, encode, index, report (M13.3).

`VoicePaths.for_root(root)` names every location: the config (data/voice/scribe.json), the raw
WAV cache and the report (gitignored artifacts/voice/raw and artifacts/voice/report) and the
output folder the game serves (aidm/web/static/audio/voice/scribe). `fetch_raw` returns the cached
raw WAV of a line or asks the provider once and caches it atomically; with `provider=None`
(--reprocess) a missing cache entry raises `MissingRaw` naming the line, so a reprocess never
calls the API. `build_line` processes one raw WAV, encodes `<line_id>.mp3` once, writes the
spectrogram and the line report and returns the index entry.

Public API: `VoicePaths`, `MissingRaw`, `LineBuild`, `raw_path`, `fetch_raw`, `build_line`,
`build_lines`.
"""

from __future__ import annotations

import os
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
from aidm.server.voicegen.provider import TtsProvider, read_wav
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


class MissingRaw(LookupError):
    """--reprocess found no cached raw WAV for a line."""


@dataclass(frozen=True)
class LineBuild:
    entry: IndexEntry
    metrics: LineMetrics
    problems: tuple[str, ...]


def raw_path(paths: VoicePaths, line: VoiceLine) -> Path:
    return paths.raw_dir / line.raw_name


def fetch_raw(paths: VoicePaths, line: VoiceLine, provider: TtsProvider | None) -> bytes:
    path = raw_path(paths, line)
    if path.is_file():
        return path.read_bytes()
    if provider is None:
        raise MissingRaw(f"{line.id}: no cached raw WAV ({path.name}); run with --yes")
    data = provider.synthesize(line.text, line.voice)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return data


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
