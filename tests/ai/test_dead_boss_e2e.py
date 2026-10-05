"""v1 regression, end to end (SPEC 13): a boss killed in a fight is never narrated alive again."""

from __future__ import annotations

from pathlib import Path

from aidm.dm.epilogue import write_epilogue
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import check_prose
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate
from aidm.models.events import CreatureDied
from aidm.rules.progression import boss_defeated
from tests.ai.epilogue_fixtures import FINAL_BOSS, finished_campaign
from tests.ai.fake_scripts import fake_client
from tests.session.progression_fixtures import plan

ALIVE_VERBS = ("rises", "roars", "stands", "laughs", "lunges", "charges", "snarls")
ZOMBIE_TURN = (
    f"{FINAL_BOSS} rises from the stones and roars at you. {FINAL_BOSS} lunges at the party."
)
ZOMBIE_EPILOGUE = (
    f"{FINAL_BOSS} still stands at the gateway, laughing at the heroes. "
    f"{FINAL_BOSS} charges once more and the beacon dies."
)


def _alive_words(text: str) -> list[str]:
    return [w for w in ALIVE_VERBS if w in text.lower()]


async def test_v1_dead_boss_never_described_alive_end_to_end(tmp_path: Path) -> None:
    _, state, _, final = finished_campaign()
    boss_region = plan().acts[2].region
    boss = next(c for c in state.creatures.values() if c.name == FINAL_BOSS)
    assert boss.dead and boss_defeated(state, boss_region)
    assert any(isinstance(e, CreatureDied) and e.creature_id == boss.id for e in final)

    # 1. the kill turn: an adversarial model brings the boss back to life, twice.
    client, fake = fake_client(tmp_path, [fake_text(ZOMBIE_TURN), fake_text(ZOMBIE_TURN)])
    stream = narrate(state, final, client)
    text = await stream.collect()
    assert stream.source is NarrationSource.TEMPLATE and stream.retried and len(fake.requests) == 2
    kinds = {v.kind for r in stream.reports for v in r.violations}
    assert ViolationKind.DEAD_ACTING in kinds
    assert not _alive_words(text)
    assert ViolationKind.DEAD_ACTING not in {v.kind for v in check_prose(text, state).violations}

    # 2. the epilogue: the same lie about the dead boss is caught and replaced by the facts.
    client, fake = fake_client(tmp_path, [fake_text(ZOMBIE_EPILOGUE), fake_text(ZOMBIE_EPILOGUE)])
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.TEMPLATE
    assert ViolationKind.DEAD_ACTING in {v.kind for r in result.reports for v in r.violations}
    assert FINAL_BOSS in result.text and f"{FINAL_BOSS} was defeated" in result.text
    assert not _alive_words(result.text)
    assert len(fake.requests) == 2
