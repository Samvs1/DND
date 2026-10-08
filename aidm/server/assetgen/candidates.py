"""Turn staged generator output into one reviewable image per key (Addendum B.5).

`collect` reads the runner's candidate images with their JSON sidecars. A single image is fitted to
the manifest target size; a 4x4 sheet is sliced (slicer.py) with cell i going to `keys[i]`. Every
per-key image is written under the slices directory (atomically) and returned as a `Candidate`
with its attempt number: the n-th staged image for that key, in staging file order.

Public API: `Candidate`, `collect`, `write_atomic`, `target_size`.
"""

import io
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from aidm.server.assetgen.slicer import fit_cell, png_bytes, slice_sheet


@dataclass(frozen=True)
class Candidate:
    key: str
    attempt: int
    image: Path
    model: str
    prompt: str
    cost_eur: float


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def target_size(entry: Mapping[str, Any]) -> tuple[int, int] | None:
    size = entry.get("size")
    if isinstance(size, list) and len(size) == 2:
        return int(size[0]), int(size[1])
    return None


def _images_of(
    meta: Mapping[str, Any], data: bytes, manifest: Mapping[str, Mapping[str, Any]]
) -> dict[str, bytes]:
    sizes = {k: s for k in meta["keys"] if k in manifest and (s := target_size(manifest[k]))}
    if meta.get("sheet"):
        cuts = slice_sheet(
            data, list(meta["keys"]), {k: sizes.get(k, (64, 64)) for k in meta["keys"]}
        )
        return {k: v for k, v in cuts.items() if k in sizes}
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    return {k: png_bytes(fit_cell(image, s)) for k, s in sizes.items()}


def collect(
    staging: Path, slices_dir: Path, manifest: Mapping[str, Mapping[str, Any]]
) -> list[Candidate]:
    """Per-key candidate images for every staged sidecar (sheets sliced, singles fitted)."""
    found: list[Candidate] = []
    attempts: dict[str, int] = {}
    for sidecar in sorted(staging.glob("*.json")):
        png = sidecar.with_suffix(".png")
        if not png.is_file():
            continue
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        share = float(meta.get("cost_eur", 0.0)) / max(1, len(meta["keys"]))
        for key, data in _images_of(meta, png.read_bytes(), manifest).items():
            attempts[key] = attempts.get(key, 0) + 1
            out = slices_dir / f"{key}__a{attempts[key]}.png"
            write_atomic(out, data)
            found.append(Candidate(key, attempts[key], out, meta["model"], meta["prompt"], share))
    return found
