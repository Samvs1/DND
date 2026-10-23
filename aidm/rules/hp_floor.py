"""Features that keep a creature on its feet at the damage choke point (M29.9a T18). Pure.

`endurance(target)`: the first `drop_to_one` hook (`aidm.data.feature_hooks`) of the target's
features with a use of its resource left, as (feature id, feature name, resource key), else
None. `aidm.rules.damage.resolve_damage` asks it when damage would drop the target from above 0
to 0 HP without killing it outright (SRD 5.1 Half-Orc "Relentless Endurance": "When you are
reduced to 0 hit points but not killed outright, you can drop to 1 hit point instead"; BG3 uses
it at once, without a prompt). The feature data is read through the shared registry, as the
choke point reads condition data.

Public API: `endurance(target) -> tuple[str, str, str] | None`.
"""

from aidm.data.feature_defs import feature_defs
from aidm.data.feature_hooks import DropToOneHook
from aidm.models.state import Creature
from aidm.rules.features import creature_hooks
from aidm.rules.resources import resource_left


def endurance(target: Creature) -> tuple[str, str, str] | None:
    feats = feature_defs()
    for feature_id, hook in creature_hooks(target, feats):
        if isinstance(hook, DropToOneHook) and resource_left(target, hook.resource) >= 1:
            return feature_id, feats.get(feature_id).name, hook.resource
    return None
