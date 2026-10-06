"""The party simulation (M9.1) as a test: one seed, fake AI, three real-websocket bots."""

import pytest

from scripts.sim.run import SimOptions, run_seed


@pytest.mark.sim
async def test_simulate_party_one_seed_fake_ai() -> None:
    report = await run_seed(1, SimOptions(timeout=30.0))
    assert report.ok, "\n".join(report.failures)
    assert report.combats >= 1
    assert report.turns >= 20
