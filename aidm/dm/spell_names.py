"""The spell or feature a typed line names (M31.1a V1, V2): matched on the names the hero has
READY, so it is data-driven (no spell is named in code).

- `ready_spells(actor)`: (index, name) of the hero's ready spells: cantrips and prepared or
  known spells of the ONE sheet builder (`rules.sheet_spells.spellcasting_block`), racial and
  feature spells too;
- `targeted_features(actor)`: (feature id, name) of the active abilities the hotbar offers
  that aim at others (Turn Undead);
- `said_name(words, options)`: the option whose name words stand together in the line, the
  longest name first, unless a veto word of the lexicon's `spell_name_vetoes` stands just
  before it ("I ask about sacred flame" casts nothing). Returns (key, name, span).

Public API: `Option`, `ready_spells`, `targeted_features`, `said_name`.
"""

from aidm.data.combat_data import combat_registries
from aidm.data.intent_phrases import intent_phrases
from aidm.dm.fight_names import name_span
from aidm.models.state import Creature
from aidm.rules.features import feature_actions
from aidm.rules.sheet_spells import spellcasting_block

type Option = tuple[str, str]
type Said = tuple[str, str, tuple[int, int]]
_LOOK_BACK = 3


def ready_spells(actor: Creature) -> list[Option]:
    block = spellcasting_block(actor, combat_registries().chars)
    if block is None:
        return []
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    return [(s.index, s.name) for s in lines if s.prepared]


def targeted_features(actor: Creature) -> list[Option]:
    feats = combat_registries().chars.features
    return [
        (o.feature, o.name)
        for o in feature_actions(actor, feats)
        if o.command and o.action == "ability" and o.target_kind != "self" and o.name
    ]


def said_name(words: list[str], options: list[Option]) -> Said | None:
    vetoes = intent_phrases().lexicon["spell_name_vetoes"]
    found: list[tuple[int, int, Said]] = []
    for key, name in options:
        span = name_span(words, name)
        if span is None or set(words[max(0, span[0] - _LOOK_BACK) : span[0]]) & vetoes:
            continue
        found.append((span[0] - span[1], span[0], (key, name, span)))
    return min(found)[2] if found else None
