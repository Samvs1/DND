"""d20 tests: advantage/disadvantage cancellation and the d20 roll itself.

Public API:
- `combine_adv(adv_sources, dis_sources) -> AdvState`: SRD 5.1 "Advantage and Disadvantage":
  if at least one source grants advantage and at least one imposes disadvantage, the roll is
  NORMAL regardless of how many of each; otherwise any advantage -> ADVANTAGE, any
  disadvantage -> DISADVANTAGE, none -> NORMAL. Counts must be >= 0.
- `roll_d20(rng, adv=NORMAL, modifier=0, *, crit_on=20) -> D20Roll`: rolls one d20 (NORMAL) or two
  (ADVANTAGE keeps the higher, DISADVANTAGE the lower); both dice are recorded in `rolls`.
  `is_crit` is natural >= `crit_on` (20 by default; lowered by features such as Improved Critical),
  `is_fumble` is natural 1. Whether a crit or fumble matters (attacks, BG3 checks) is decided by the
  caller, not here.
"""

from aidm.models.dice import AdvState, D20Roll
from aidm.rules.dice import Rng


def combine_adv(adv_sources: int, dis_sources: int) -> AdvState:
    if adv_sources < 0 or dis_sources < 0:
        raise ValueError("advantage source counts must be >= 0")
    if adv_sources and dis_sources:
        return AdvState.NORMAL
    if adv_sources:
        return AdvState.ADVANTAGE
    if dis_sources:
        return AdvState.DISADVANTAGE
    return AdvState.NORMAL


def roll_d20(
    rng: Rng, adv: AdvState = AdvState.NORMAL, modifier: int = 0, *, crit_on: int = 20
) -> D20Roll:
    if not 2 <= crit_on <= 20:
        raise ValueError("crit_on must be between 2 and 20")
    first = rng.randint(1, 20)
    if adv is AdvState.NORMAL:
        rolls = (first,)
        natural = first
    else:
        rolls = (first, rng.randint(1, 20))
        natural = max(rolls) if adv is AdvState.ADVANTAGE else min(rolls)
    return D20Roll(
        rolls=rolls,
        adv=adv,
        natural=natural,
        modifier=modifier,
        total=natural + modifier,
        is_crit=natural >= crit_on,
        is_fumble=natural == 1,
    )
