"""Helper for data/bg3/encounter_monsters.json (M3.9): print the encounter-ready candidates.

The JSON is the source of truth and is hand-curated; this script lists every SRD monster with
CR <= 8 together with its catalog status so the curator can pick entries.
Usage: python scripts/build_monster_catalog.py [--ready-only]
"""

from __future__ import annotations

import io
import sys

from aidm.data.combat_data import combat_registries
from aidm.rules.monster_catalog import monster_catalog

MAX_CR = 8


def _tier(cr: float) -> int:
    return 1 if cr <= 1 else 2 if cr <= 4 else 3


def main() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    ready_only = "--ready-only" in sys.argv
    regs = combat_registries()
    for block in sorted(regs.monsters.all(), key=lambda m: (m.challenge_rating, m.index)):
        if block.challenge_rating > MAX_CR:
            continue
        cat = monster_catalog(block, regs.monster_overlay, regs.spells)
        shapes = sorted({o.shape for o in cat.options})
        if not [o for o in cat.options if o.shape != "spell"]:
            continue
        if ready_only and cat.unsupported:
            continue
        immune = "; ".join([*block.damage_immunities, *block.damage_resistances])
        print(
            f"T{_tier(block.challenge_rating)} cr={block.challenge_rating:<5} {block.index:<28}"
            f" {block.type:<12} {','.join(shapes):<28} unsup={list(cat.unsupported)}"
            f" def=[{immune}]"
        )


if __name__ == "__main__":
    main()
