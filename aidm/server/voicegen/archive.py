"""Lossless archive of the approved raw takes (owner: "commit them so we have a paper trail").

The raw cache (artifacts/voice/raw) is gitignored and local. Every raw WAV the config uses (a
line's recording, or each part of a spliced line) is also kept as FLAC in the tracked folder
`data/voice/takes/<raw stem>.flac`, so a fresh clone can rebuild every line bit for bit with
`--reprocess` (no new API calls, no lost performances) and the history of each take is in git.

- `to_flac` / `from_flac`: lossless; 16- and 24-bit PCM keep their samples exactly (anything
  else is stored as 24-bit PCM).
- `archive_used(raw_paths, archive_dir)`: writes the FLAC of every cached raw that is not archived
  yet; returns the names written. Runs after every build.
- `restore(raw_path, archive_dir)`: the WAV bytes of an archived take, or None.
- `missing(raw_paths, archive_dir)`: names of used raws without an archive entry (`--check`).
- `orphans(raw_paths, archive_dir)`: archived takes the config no longer uses (reported, kept:
  the paper trail is append only).

Public API: `to_flac`, `from_flac`, `archive_path`, `archive_used`, `restore`, `missing`,
`orphans`.
"""

from __future__ import annotations

import io
import os
from collections.abc import Sequence
from pathlib import Path

import soundfile as sf

EXACT = ("PCM_16", "PCM_24")


def _convert(data: bytes, fmt: str) -> bytes:
    info = sf.info(io.BytesIO(data))
    subtype = info.subtype if info.subtype in EXACT else "PCM_24"
    if subtype == "PCM_16":
        samples, rate = sf.read(io.BytesIO(data), dtype="int16", always_2d=False)
    else:
        samples, rate = sf.read(io.BytesIO(data), dtype="int32", always_2d=False)
    out = io.BytesIO()
    sf.write(out, samples, rate, format=fmt, subtype=subtype)
    return out.getvalue()


def to_flac(wav: bytes) -> bytes:
    return _convert(wav, "FLAC")


def from_flac(flac: bytes) -> bytes:
    return _convert(flac, "WAV")


def archive_path(raw_path: Path, archive_dir: Path) -> Path:
    return archive_dir / f"{raw_path.stem}.flac"


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def archive_used(raw_paths: Sequence[Path], archive_dir: Path) -> list[str]:
    written: list[str] = []
    for raw in raw_paths:
        target = archive_path(raw, archive_dir)
        if raw.is_file() and not target.is_file():
            _atomic(target, to_flac(raw.read_bytes()))
            written.append(target.name)
    return written


def restore(raw_path: Path, archive_dir: Path) -> bytes | None:
    source = archive_path(raw_path, archive_dir)
    return from_flac(source.read_bytes()) if source.is_file() else None


def missing(raw_paths: Sequence[Path], archive_dir: Path) -> list[str]:
    return [raw.name for raw in raw_paths if not archive_path(raw, archive_dir).is_file()]


def orphans(raw_paths: Sequence[Path], archive_dir: Path) -> list[str]:
    used = {archive_path(raw, archive_dir).name for raw in raw_paths}
    found = sorted(p.name for p in archive_dir.glob("*.flac")) if archive_dir.is_dir() else []
    return [name for name in found if name not in used]
