"""Build aidm/web/static/assets/manifest.json from the data registries (Addendum A.2).

One entry per asset key (see aidm/server/asset_keys.py). An entry is `real` when its file exists
under aidm/web/static and `placeholder` otherwise; `prompt`, `source` and `license` of existing
entries are preserved on rebuild. Existing v1 files are recognised (source v1). A placeholder entry
with no prompt gets one from `aidm/server/asset_prompts.py` (style bible prefix + subject details
from the data); `--refresh-prompts` rebuilds the prompt of EVERY placeholder entry (use after
editing docs/STYLE_BIBLE.md; hand-written prompts of placeholders are replaced).

Usage: python scripts/build_manifest.py [--check] [--refresh-prompts]
(--check exits 1 when the manifest is stale)
"""

from __future__ import annotations

import io
import json
import struct
import sys
from pathlib import Path
from typing import Any

from aidm.server.asset_keys import AssetSpec, derive_specs
from aidm.server.asset_prompts import build_prompt

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
V1_LICENSE = "v1 project asset (owner's own)"
MANIFEST_PARTS = ("static", "assets", "manifest.json")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_web_root() -> Path:
    return repo_root() / "aidm" / "web"


def manifest_path(web_root: Path) -> Path:
    return web_root.joinpath(*MANIFEST_PARTS)


def png_size(path: Path) -> list[int] | None:
    with path.open("rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != PNG_MAGIC:
        return None
    width, height = struct.unpack(">II", head[16:24])
    return [int(width), int(height)]


def load_existing(web_root: Path) -> dict[str, dict[str, Any]]:
    path = manifest_path(web_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def build_entry(
    spec: AssetSpec, static_dir: Path, old: dict[str, Any], *, refresh_prompt: bool = False
) -> dict[str, Any]:
    target = static_dir / spec.file
    real = target.is_file()
    size = list(spec.size) if spec.size else None
    if real and size is not None:
        size = png_size(target) or size
    source = str(old.get("source") or "")
    if not source and real:
        source = "v1" if spec.v1 else "manual"
    elif not source and spec.hand:
        source = "manual"
    licence = str(old.get("license") or (V1_LICENSE if source == "v1" else ""))
    prompt = "" if refresh_prompt and not real else str(old.get("prompt") or "")
    if not prompt and not real:
        prompt = build_prompt(spec)
    entry: dict[str, Any] = {
        "kind": spec.kind,
        "file": spec.file,
        "size": size,
        "transparent": spec.transparent,
        "status": "real" if real else "placeholder",
        "prompt": prompt,
        "source": source,
        "license": licence,
    }
    if real and source.startswith("generated:"):
        entry.update({k: old[k] for k in ("reviewed", "cost_eur") if k in old})
    return entry


def build_manifest(web_root: Path, *, refresh_prompts: bool = False) -> dict[str, dict[str, Any]]:
    static_dir = web_root / "static"
    old = load_existing(web_root)
    return {
        spec.key: build_entry(
            spec, static_dir, old.get(spec.key, {}), refresh_prompt=refresh_prompts
        )
        for spec in derive_specs(static_dir)
    }


def render(manifest: dict[str, dict[str, Any]]) -> str:
    return json.dumps(manifest, indent=1) + "\n"


def counts(manifest: dict[str, dict[str, Any]]) -> tuple[int, int]:
    real = sum(1 for e in manifest.values() if e["status"] == "real")
    return real, len(manifest) - real


def run(web_root: Path, *, check: bool, refresh_prompts: bool = False) -> int:
    manifest = build_manifest(web_root, refresh_prompts=refresh_prompts)
    text = render(manifest)
    path = manifest_path(web_root)
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    real, placeholder = counts(manifest)
    summary = f"{len(manifest)} entries, {real} real, {placeholder} placeholder"
    if check:
        if current == text:
            print(f"manifest: ok ({summary})")
            return 0
        print("manifest: STALE, run python scripts/build_manifest.py")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"manifest: wrote {path.name} ({summary})")
    return 0


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    return run(
        default_web_root(), check="--check" in argv, refresh_prompts="--refresh-prompts" in argv
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
