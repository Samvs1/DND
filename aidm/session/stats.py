"""Token totals for the host panel (SPEC 4 DeepSeek, 10 host controls).

Public API: `host_stats(core) -> HostStats`, `send_host_stats(core)` (to every host seat).
"""

from aidm.models.protocol_server import HostStats
from aidm.session.table_core import TableCore


def host_stats(core: TableCore) -> HostStats:
    totals = list(core.llm.totals.by_role.values())
    return HostStats(
        prompt_tokens=sum(t.prompt_tokens for t in totals),
        completion_tokens=sum(t.completion_tokens for t in totals),
        calls=sum(t.calls for t in totals),
    )


def send_host_stats(core: TableCore) -> None:
    stats = host_stats(core)
    for player in core.players.values():
        if player.is_host:
            core.send(player.id, stats)
