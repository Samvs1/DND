"""`lines.json`, the index of the built voice files, and the offline staleness check (M13.3).

The index sits next to the mp3 files (aidm/web/static/audio/voice/scribe/lines.json) and holds,
per line in config order: id, text_sha, chain_sha (resolved chain + voice settings), file,
sha256, duration_s, lufs, true_peak_db. `check` needs no network and no DSP: a configured line
without a file or entry, a text or chain hash that differs from the config, a file whose sha256
differs from the index, or an index entry for a line no longer configured is one problem each.

Public API: `INDEX_NAME`, `IndexEntry`, `load_index`, `write_index`, `merge_entries`, `check`,
`file_sha256`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from aidm.server.voicegen.config import VoiceConfig

INDEX_NAME = "lines.json"
SOURCE = "Built by scripts/gen_scribe_voice.py from data/voice/scribe.json. Do not edit."


class IndexEntry(TypedDict):
    id: str
    text_sha: str
    chain_sha: str
    file: str
    sha256: str
    duration_s: float
    lufs: float
    true_peak_db: float


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_index(out_dir: Path) -> dict[str, IndexEntry]:
    path = out_dir / INDEX_NAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data.get("lines", [])}


def merge_entries(
    config: VoiceConfig, old: dict[str, IndexEntry], new: Iterable[IndexEntry]
) -> list[IndexEntry]:
    """Old entries updated by the new ones, in config order; unconfigured ids are dropped."""
    merged = dict(old)
    for entry in new:
        merged[entry["id"]] = entry
    return [merged[line_id] for line_id in config.ids() if line_id in merged]


def write_index(out_dir: Path, entries: list[IndexEntry]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / INDEX_NAME
    tmp = path.with_name(f"{INDEX_NAME}.{os.getpid()}.tmp")
    text = json.dumps({"source": SOURCE, "lines": entries}, indent=2) + "\n"
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def _line_problems(
    entry: IndexEntry | None, line_id: str, sha: tuple[str, str], out_dir: Path
) -> list[str]:
    if entry is None:
        return [f"{line_id}: not in {INDEX_NAME} (run gen_scribe_voice.py --yes)"]
    problems: list[str] = []
    if entry["text_sha"] != sha[0]:
        problems.append(f"{line_id}: text changed since the build")
    if entry["chain_sha"] != sha[1]:
        problems.append(f"{line_id}: chain or voice settings changed since the build")
    path = out_dir / entry["file"]
    if not path.is_file():
        problems.append(f"{line_id}: missing {entry['file']}")
    elif file_sha256(path) != entry["sha256"]:
        problems.append(f"{line_id}: {entry['file']} differs from {INDEX_NAME} (edited by hand?)")
    return problems


def check(config: VoiceConfig, out_dir: Path) -> list[str]:
    """One ASCII line per problem; empty when every configured line is built and current."""
    index = load_index(out_dir)
    problems: list[str] = []
    for line in config.lines:
        sha = (line.text_sha, line.chain_sha)
        problems += _line_problems(index.get(line.id), line.id, sha, out_dir)
    for stale in sorted(set(index) - set(config.ids())):
        problems.append(f"{stale}: in {INDEX_NAME} but not in the config")
    return problems
