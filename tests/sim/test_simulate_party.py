"""The party simulation (M9.1) as a test: one seed, fake AI, three real-websocket bots.
M27.10: the bots use their gear (a torch in the dark, oil and a thrown torch, a healer's kit)."""

import pytest

from scripts.sim.run import SimOptions, run_seed


@pytest.mark.sim
async def test_simulate_party_one_seed_fake_ai() -> None:
    report = await run_seed(1, SimOptions(timeout=30.0))
    assert report.ok, "\n".join(report.failures)
    assert report.combats >= 1
    assert report.turns >= 20
    # M9.2: a level-up and both rests are reached by play (no difficulty or XP crutch).
    assert report.level >= 2
    assert report.rests[0] >= 1 and report.rests[1] >= 1
    # M27.10 gear (the engine's own log is checked by `scripts.sim.gear.gear_failures`).
    gear = report.gear
    assert gear["dark_places"] >= 1 and gear["torch_lit"] >= 1 and gear["doused"] >= 1
    assert gear["oil-flask-throw"] + gear["torch-throw"] >= 1
    assert gear["healers-kit-stabilize"] >= 1 or gear["kit_chances"] == 0
    assert gear["refused"] == 0
