"""The simulation's own assertions catch what they claim to catch (M9.1)."""

from pathlib import Path

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.state import GameState
from aidm.rules.campaign_install import install_campaign
from aidm.session.persistence import CampaignStore
from aidm.session.reducer import apply
from scripts.sim.checks import engine_invariants, privacy_leaks, public_invariants, replay_problems


def test_public_invariants_flag_hp_outside_range() -> None:
    state = {"party": [{"id": "pc-1", "hp": 12, "max_hp": 10, "temp_hp": 0}], "combat": None}
    assert len(public_invariants(state)) == 1
    state["party"][0]["hp"] = 10
    assert public_invariants(state) == []


def test_public_invariants_flag_token_hp() -> None:
    combat = {"tokens": [{"creature_id": "rat-1", "hp": -1, "max_hp": 5}]}
    assert len(public_invariants({"party": [], "combat": combat})) == 1


def test_engine_invariants_pass_on_an_empty_game() -> None:
    assert engine_invariants(GameState(campaign_id="c-empty", seed=1)) == []


def _installed_game() -> GameState:
    state = GameState(campaign_id="c-priv", seed=3)
    for event in install_campaign(state, load_sample_campaign(), 3):
        apply(state, event)
    return state


def test_privacy_leaks_finds_a_hidden_motive_and_secret() -> None:
    game = _installed_game()
    plan = load_sample_campaign()
    npc = next(n for n in plan.npcs if n.secrets)
    assert privacy_leaks(game, ["the harbour is quiet tonight"]) == []
    assert privacy_leaks(game, [f'{{"text": "{npc.motive}"}}']) == [
        f"private text reached a client: {npc.id} motive"
    ]
    secret = npc.secrets[0]
    spaced = secret.text.replace(" ", "  ").upper()
    assert any(secret.id in leak for leak in privacy_leaks(game, [spaced]))


def test_privacy_leaks_ignores_a_revealed_secret() -> None:
    game = _installed_game()
    npc = next(n for n in game.world.npcs.values() if n.secrets)
    text = npc.secrets[0].text
    assert any(npc.secrets[0].id in leak for leak in privacy_leaks(game, [text]))
    npc.secrets[0].revealed = True
    assert not any(npc.secrets[0].id in leak for leak in privacy_leaks(game, [text]))


def test_replay_problems_reports_a_missing_save(tmp_path: Path) -> None:
    live = GameState(campaign_id="c-missing", seed=1)
    assert CampaignStore(tmp_path).exists("c-missing") is False
    assert replay_problems(tmp_path, "c-missing", live) == ["no save folder for c-missing"]
