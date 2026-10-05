"""Ready votes for party-level actions: travel, rest, shop (SPEC 10).

One vote at a time. Voters are the connected players with a living hero when the vote opens;
the proposer counts as ready. The vote PASSES as soon as a strict majority is ready and FAILS
as soon as half or more declined (a majority is then impossible). When the timer runs out
(default 30 s, `TableConfig.vote_seconds`) it passes if more voters are ready than declined:
silence abstains, so an idle player never blocks the table. The host can force a pass. A voter
who disconnects is dropped and the tally is re-checked. A passed vote schedules its job.

Public API: `eligible_voters`, `open_vote`, `cast_vote`, `force_vote`, `vote_timeout`,
`drop_voter`, `close_vote`.
"""

from aidm.models.protocol_server import (
    ErrorCode,
    NoticeKind,
    VoteClosed,
    VoteOpen,
    VoteUpdate,
)
from aidm.models.protocol_views import VoteKind
from aidm.session.table_core import Job, OpenVote, Player, TableCore


def eligible_voters(core: TableCore) -> list[str]:
    return sorted(
        p.id for p in core.players.values() if p.connected and core.living_pc(p) is not None
    )


def open_vote(core: TableCore, kind: VoteKind, detail: str, proposer: Player, job: Job) -> bool:
    if core.vote is not None:
        core.notice(proposer.id, NoticeKind.REFUSED, "Another vote is already open.")
        return False
    voters = eligible_voters(core)
    if proposer.id not in voters:
        voters = sorted([*voters, proposer.id])
    seconds = core.config.vote_seconds
    vote = OpenVote(core.next_id("v"), kind, detail, proposer.id, voters, job, seconds=seconds)
    vote.ready.add(proposer.id)
    vote.timer = core.start_timer("vote", vote.id, seconds)
    core.vote = vote
    core.broadcast(
        VoteOpen(
            vote_id=vote.id,
            kind=kind,
            detail=detail,
            proposer_id=proposer.id,
            voters=tuple(voters),
            seconds=seconds,
        )
    )
    _settle(core, vote)
    return True


def cast_vote(core: TableCore, player: Player, vote_id: str, ready: bool) -> None:
    vote = core.vote
    if vote is None or vote.id != vote_id or player.id not in vote.voters:
        core.error(player.id, ErrorCode.NO_VOTE, "There is no vote for you to answer.")
        return
    (vote.declined if not ready else vote.ready).add(player.id)
    (vote.ready if not ready else vote.declined).discard(player.id)
    core.broadcast(
        VoteUpdate(
            vote_id=vote.id, ready=tuple(sorted(vote.ready)), declined=tuple(sorted(vote.declined))
        )
    )
    _settle(core, vote)


def force_vote(core: TableCore, host: Player) -> None:
    if core.vote is None:
        core.error(host.id, ErrorCode.NO_VOTE, "There is no open vote.")
        return
    close_vote(core, passed=True, reason="forced by the host")


def vote_timeout(core: TableCore, vote_id: str) -> None:
    vote = core.vote
    if vote is None or vote.id != vote_id:
        return
    close_vote(core, passed=len(vote.ready) > len(vote.declined), reason="time is up")


def drop_voter(core: TableCore, player_id: str) -> None:
    vote = core.vote
    if vote is None or player_id not in vote.voters or player_id == vote.proposer_id:
        return
    vote.voters.remove(player_id)
    vote.ready.discard(player_id)
    vote.declined.discard(player_id)
    _settle(core, vote)


def _settle(core: TableCore, vote: OpenVote) -> None:
    n = len(vote.voters)
    if 2 * len(vote.ready) > n:
        close_vote(core, passed=True, reason="the party is ready")
    elif 2 * len(vote.declined) >= n:
        close_vote(core, passed=False, reason="the party declined")


def close_vote(core: TableCore, *, passed: bool, reason: str) -> None:
    vote = core.vote
    if vote is None:
        return
    core.vote = None
    if vote.timer is not None:
        vote.timer.cancel()
    core.broadcast(VoteClosed(vote_id=vote.id, passed=passed, reason=reason))
    if passed:
        core.schedule(vote.on_pass)
    else:
        core.notice(None, NoticeKind.INFO, f"The party stays put: {reason}.")
