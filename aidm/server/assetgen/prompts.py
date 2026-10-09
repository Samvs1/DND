"""Generation prompts and style references (Addendum B.3).

Every prompt starts with the style bible prefix (docs/STYLE_BIBLE.md, loaded through
`aidm.server.asset_prompts`, the same source the manifest prompts and ASSETS_TODO.md use). Subjects
come from the data (`build_subject`). Portraits and scenes go through the edit endpoint with 2-3
real v1 images of the same kind (copies under aidm/web/static) and the fixed reference sentence;
sheets use one v1 sheet (the read-only v1 project, `assets_src/sheets`). A missing reference file
is simply left out; with none left the call falls back to the generate endpoint.
A few keys draw their references from a character's own art instead of the kind's (`KEY_REFS`,
M13.6: the Scribe's poses use his owner-made seated portrait and wide scene, so his core look
stays: skeletal face, deep purple hood and robe, glowing violet eyes, quill and ledger).

Public API: `RefSources`, `references_for`, `spec_of`, `single_prompt`, `sheet_prompt`,
`REFERENCE_TEXT`, `SINGLE_KINDS`, `KEY_REFS`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidm.server.asset_keys import AssetSpec, split_key
from aidm.server.asset_prompts import StyleBible, build_subject
from aidm.server.assetgen.provider import SHEET_MARK

REFERENCE_TEXT = (
    "Match the style, palette, lighting, framing and painterly quality of the reference images "
    "exactly."
)
SHEET_REFERENCE_TEXT = (
    "Match the style, palette, outline weight, lighting and finish of the reference sheet exactly."
)
PORTRAIT_REFS = (
    "img/portraits/fighter_cropped.png",
    "img/portraits/rogue_cropped.png",
    "img/portraits/wizard_cropped.png",
)
SCENE_REFS = ("img/portraits/ranger_cropped.png", "img/portraits/cleric_cropped.png")
STATIC_REFS = {
    "portrait": PORTRAIT_REFS,
    "region_banner": SCENE_REFS,
    "zone_card": SCENE_REFS,
    "scene": SCENE_REFS,
}
SINGLE_KINDS = frozenset(STATIC_REFS)
SCRIBE_REFS = ("img/portraits/scribe_seated.png", "img/scenes/scribe.png")
KEY_REFS = {
    "portrait.scribe.welcome": SCRIBE_REFS,
    "portrait.scribe.rewrite": SCRIBE_REFS,
}
V1_SHEET = ("assets_src", "sheets", "overhaul_sheet.png")


@dataclass(frozen=True)
class RefSources:
    static_dir: Path
    v1_root: Path | None = None


def references_for(kind: str, sources: RefSources, key: str = "") -> tuple[Path, ...]:
    """Existing reference files for a key (`KEY_REFS`), its kind, or the v1 sheet for a sheet."""
    if key in KEY_REFS:
        paths = [sources.static_dir / rel for rel in KEY_REFS[key]]
    elif kind in STATIC_REFS:
        paths = [sources.static_dir / rel for rel in STATIC_REFS[kind]]
    elif sources.v1_root is not None:
        paths = [sources.v1_root.joinpath(*V1_SHEET)]
    else:
        paths = []
    return tuple(p for p in paths if p.is_file())


def spec_of(key: str, entry: Mapping[str, Any]) -> AssetSpec:
    size = entry.get("size")
    dims = (int(size[0]), int(size[1])) if size else None
    return AssetSpec(
        key, split_key(key)[0], str(entry["file"]), dims, bool(entry.get("transparent"))
    )


def _finish(spec: AssetSpec) -> str:
    crop = ""
    if spec.size is not None:
        crop = f" Compose for a final crop to {spec.size[0]}x{spec.size[1]}."
    return crop + (" Transparent background." if spec.transparent else "")


def single_prompt(bible: StyleBible, spec: AssetSpec, *, with_refs: bool) -> str:
    """Prompt for one portrait, banner or zone card."""
    subject = build_subject(spec)
    note = bible.kinds.get(spec.kind, "")
    if with_refs:
        body = f"{REFERENCE_TEXT} Create a new subject: {subject}."
    else:
        body = f"Subject: {subject}."
    return f"{bible.prefix} {body} {note}{_finish(spec)}".strip()


def sheet_prompt(
    bible: StyleBible, specs: Sequence[AssetSpec], *, with_ref: bool, cells: int = 16
) -> str:
    """Prompt for one 4x4 sheet: one subject per cell in reading order."""
    listed = "; ".join(f"{i}: {build_subject(s)}" for i, s in enumerate(specs, start=1))
    notes = " ".join(dict.fromkeys(bible.kinds.get(s.kind, "") for s in specs)).strip()
    empty = f" Leave cells {len(specs) + 1} to {cells} empty." if len(specs) < cells else ""
    ref = f" {SHEET_REFERENCE_TEXT}" if with_ref else ""
    transparent = " Transparent background." if any(s.transparent for s in specs) else ""
    return (
        f"{bible.prefix} A {SHEET_MARK}: a square image split into an even 4 by 4 grid of "
        f"{cells} equal cells, one separate subject centred in each cell with clear empty space "
        f"around it, nothing crossing a cell border, no grid lines, no labels.{ref} Cells in "
        f"reading order (left to right, top to bottom): {listed}.{empty} {notes}{transparent}"
    ).strip()
