"""The dice sound names (M26.8): the `sfx.<name>` manifest keys and `audio/sfx/<name>.mp3` files.
Plain data (no numpy), read by aidm/server/asset_keys.py; aidm/server/sfxgen/catalog.py builds
exactly these.

Public API: `DICE_SFX`.
"""

DICE_SFX = (
    *(f"dice_throw_{i}" for i in range(1, 7)),
    *(f"dice_throw_two_{i}" for i in range(1, 4)),
    *(f"dice_clack_{i}" for i in range(1, 5)),
    "roll_success",  # one file, always the same (the owner signs off on exact sounds)
    "roll_failure_1",
    "roll_failure_2",
    "roll_natural_20",
    "roll_natural_1",
    "hit",
    "hit_2",
    "miss",
    "miss_2",
    "crit",
)
