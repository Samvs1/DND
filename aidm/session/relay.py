"""Read-only and relay messages of the table actor: chat, suggestions, hit chances.

Chat goes to everyone. A suggestion is a non-binding hint for the hero whose turn it is: it is
relayed only to that hero's player (SPEC 10). Hit chances are computed for the asking player's
own hero against a combatant (`rules.hit_chance.hit_chances`) and sent only to them.

Public API: `chat`, `suggest`, `hit_chances_for`.
"""

from aidm.models.protocol_client import Chat, RequestHitChances, Suggestion
from aidm.models.protocol_server import ChatRelay, ErrorCode, HitChances, SuggestionRelay
from aidm.rules.hit_chance import hit_chances
from aidm.session.table_core import Player, TableCore


def chat(core: TableCore, player: Player, msg: Chat) -> None:
    core.broadcast(ChatRelay(player_id=player.id, name=player.name, text=msg.text))


def suggest(core: TableCore, player: Player, msg: Suggestion) -> None:
    enc = core.state.encounter
    active = enc.active_id() if enc is not None and core.combat_active() else None
    owner = core.owner_of(active)
    if owner is None or owner.id == player.id:
        core.error(player.id, ErrorCode.REFUSED, "There is no other hero to advise right now.")
        return
    core.send(owner.id, SuggestionRelay(player_id=player.id, name=player.name, text=msg.text))


def hit_chances_for(core: TableCore, player: Player, msg: RequestHitChances) -> None:
    enc = core.state.encounter
    pc = core.living_pc(player)
    if enc is None or not core.combat_active() or pc is None:
        core.error(player.id, ErrorCode.WRONG_PHASE, "Hit chances are shown during a fight.")
        return
    if msg.target_id not in enc.combatants or pc.id not in enc.combatants:
        core.error(player.id, ErrorCode.UNKNOWN_TARGET, "That target is not in this fight.")
        return
    chances = hit_chances(core.state, pc.id, msg.target_id, core.regs.combat.chars)
    reply = HitChances(attacker_id=pc.id, target_id=msg.target_id, chances=tuple(chances))
    core.send(player.id, reply)
