"""The simulation's assertions: invariants, privacy, replay.

- `public_invariants(state)`: on every client snapshot, 0 <= hp <= max_hp for party and tokens.
- `engine_invariants(game)`: on the server's `GameState`, hp and every resource (spell slots,
  feature uses) within [0, maximum].
- `privacy_leaks(game, texts)`: no NPC motive or still-unrevealed secret text from the
  campaign plan appears in any message a client received (exact or whitespace-folded match).
- `replay_problems(saves_dir, campaign_id, live)`: the saved `events.jsonl` replayed from
  `initial.json` equals the live final state (and the loader did not have to recover).
- `hero_up(game, hero_id)`: the hero lives and stands (M27.10: a hero lying unconscious at
  0 HP cannot act, so its bot cannot propose, search or light anything).

Public API: `public_invariants`, `engine_invariants`, `privacy_leaks`, `replay_problems`,
`hero_up`.
"""

import json
from pathlib import Path
from typing import Any

from aidm.models.state import GameState
from aidm.session.persistence import CampaignStore
from aidm.session.reducer import replay
from scripts.sim.client import Msg


def public_invariants(state: Msg) -> list[str]:
    bad: list[str] = []
    for c in state.get("party", []):
        if not 0 <= c["hp"] <= c["max_hp"]:
            bad.append(f"party {c['id']} hp {c['hp']} outside 0..{c['max_hp']}")
        if c.get("temp_hp", 0) < 0:
            bad.append(f"party {c['id']} negative temp hp")
    for t in (state.get("combat") or {}).get("tokens", []):
        if not 0 <= t["hp"] <= t["max_hp"]:
            bad.append(f"token {t['creature_id']} hp {t['hp']} outside 0..{t['max_hp']}")
    return bad


def hero_up(game: GameState, hero_id: str) -> bool:
    hero = game.creatures.get(hero_id)
    return hero is not None and not hero.dead and hero.hp > 0


def engine_invariants(game: GameState) -> list[str]:
    bad: list[str] = []
    for cid, c in game.creatures.items():
        if not 0 <= c.hp <= c.max_hp:
            bad.append(f"{cid} hp {c.hp} outside 0..{c.max_hp}")
        for key, res in c.resources.items():
            if not 0 <= res.current <= res.maximum:
                bad.append(f"{cid} resource {key} {res.current} outside 0..{res.maximum}")
    return bad


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


def _hidden_texts(game: GameState) -> list[tuple[str, str]]:
    campaign = game.campaign
    if campaign is None:
        return []
    found: list[tuple[str, str]] = []
    for npc in campaign.plan.npcs:
        live = game.world.npcs.get(npc.id)
        revealed = {s.id for s in live.secrets if s.revealed} if live else set()
        found.append((f"{npc.id} motive", npc.motive))
        found += [(f"{npc.id} secret {s.id}", s.text) for s in npc.secrets if s.id not in revealed]
    return found


def privacy_leaks(game: GameState, texts: list[str]) -> list[str]:
    blob = "\n".join(texts)
    folded = _fold(blob)
    leaks: list[str] = []
    for label, secret in _hidden_texts(game):
        if secret and (secret in blob or _fold(secret) in folded):
            leaks.append(f"private text reached a client: {label}")
    return leaks


def message_texts(logs: list[list[Msg]]) -> list[str]:
    return [json.dumps(m, ensure_ascii=False) for log in logs for m in log]


def replay_problems(saves_dir: Path, campaign_id: str, live: GameState) -> list[str]:
    store = CampaignStore(saves_dir)
    if not store.exists(campaign_id):
        return [f"no save folder for {campaign_id}"]
    loaded = store.load(campaign_id)
    problems = [f"save needed recovery: {'; '.join(loaded.notes)}"] if loaded.recovered else []
    rebuilt = replay(loaded.initial, [entry.event for entry in loaded.log])
    if rebuilt.model_dump() != live.model_dump():
        problems.append(_first_difference(rebuilt.model_dump(), live.model_dump()))
    return problems


def _first_difference(replayed: Any, live: Any, path: str = "state") -> str:
    if isinstance(replayed, dict) and isinstance(live, dict):
        left: dict[str, Any] = replayed
        right: dict[str, Any] = live
        for key in sorted({*left, *right}):
            if left.get(key) != right.get(key):
                return _first_difference(left.get(key), right.get(key), f"{path}.{key}")
    return f"replay differs from the live state at {path}: {str(replayed)[:80]} != {str(live)[:80]}"
