"""Spoke balance statistic (M9.2, RULES_DECISIONS M9.2): a party of THREE level-1 heroes against
the tier-1 spoke offers of the sample campaign, 50 campaign seeds x every act-1 spoke.

Each seed: a fighter, a cleric (odd seeds) or wizard (even seeds) and a rogue with seeded races
and the default creation picks (no extra potions, like the party simulation), the campaign
installed with that seed, the party walks to the spoke, the world's offer is answered `fight`
and `CombatRunner` plays both sides to the end. Every offer must be rated easy or trivial and
field at most one monster per hero; the party must win at least 80% of the fights.
"""

from __future__ import annotations

import random
import sys
from collections import Counter

from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.rules.campaign_install import install_campaign
from aidm.rules.creation import build_character
from aidm.rules.offer_answer import answer_offer
from aidm.session.combat_runner import CombatRunner
from tests.session.progression_fixtures import DATA, apply_all, move, plan
from tests.sim.sim_setup import REGS
from tests.unit.rules.creation_fixtures import default_choices, race_combos

SEEDS = range(50)
MAX_ROUNDS = 50
MIN_WIN_RATE = 0.8
SPOKES = tuple(s.id for s in plan().acts[0].region.spokes)


def _party(state: GameState, seed: int) -> None:
    rng = random.Random(seed)
    for class_index in ("fighter", "cleric" if seed % 2 else "wizard", "rogue"):
        race, sub = rng.choice(race_combos())
        hero = build_character(default_choices(class_index, race, sub), REGS.chars, class_index)
        state.creatures[hero.id] = hero


def spoke_fight(seed: int, spoke: str) -> tuple[EncounterOffer, EncounterStatus]:
    state = GameState(campaign_id=f"balance-{seed}", seed=seed)
    _party(state, seed)
    apply_all(state, install_campaign(state, plan(), seed))
    move(state, spoke, [])
    assert state.campaign is not None and state.campaign.offer is not None
    offer = state.campaign.offer
    rng = random.Random(seed)
    apply_all(state, answer_offer(state, OfferChoice.FIGHT, DATA, rng, actor_id="fighter"))
    status = CombatRunner(state, REGS, rng).run(MAX_ROUNDS)
    return offer, status


def test_tier_one_spokes_are_fair_for_three_level_one_heroes() -> None:
    outcomes: Counter[EncounterStatus] = Counter()
    for seed in SEEDS:
        for spoke in SPOKES:
            offer, status = spoke_fight(seed, spoke)
            assert offer.difficulty in ("easy", "trivial"), (seed, spoke, offer)
            assert 1 <= len(offer.monster_ids) <= 3, (seed, spoke, offer.monster_ids)
            outcomes[status] += 1
    fights = sum(outcomes.values())
    rate = outcomes[EncounterStatus.VICTORY] / fights
    sys.stdout.write(
        f"SPOKE BALANCE fights={fights} victories={outcomes[EncounterStatus.VICTORY]} "
        f"defeats={outcomes[EncounterStatus.DEFEAT]} win_rate={rate:.2f}\n"
    )
    assert rate >= MIN_WIN_RATE
