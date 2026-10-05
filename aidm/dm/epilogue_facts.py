"""The facts of a finished campaign and the deterministic epilogue built from them (SPEC 9).

The epilogue may only tell what actually happened, so its input is exactly these facts and
nothing else (no motives, no unrevealed secrets, no plan flavour): how each region was resolved
(defeat or alliance), who fell and who survived, how every quest ended, where each NPC's
attitude ended (the public band only), the secrets the party really learned, and every entry of
the fact ledger. `template_epilogue` is the safe fallback: it lists the same facts in plain
past-tense sentences, and a defeated boss is only ever "defeated".

Public API:
- `RegionOutcome`, `QuestOutcome`, `EpilogueFacts` (frozen; `lines()` is the model's whole input).
- `epilogue_facts(state) -> EpilogueFacts` (ValueError without a campaign).
- `template_epilogue(facts) -> list[str]`: the deterministic fallback sentences.
"""

from dataclasses import dataclass

from aidm.models.campaign_state import RegionResolution
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.progression import boss_defeated
from aidm.rules.social import public_npc_view

MAX_LEDGER_FACTS = 24
MAX_ATTITUDES = 10


@dataclass(frozen=True)
class RegionOutcome:
    region: str
    boss: str
    how: RegionResolution | None


@dataclass(frozen=True)
class QuestOutcome:
    title: str
    state: QuestState


@dataclass(frozen=True)
class EpilogueFacts:
    title: str
    regions: tuple[RegionOutcome, ...]
    fallen: tuple[str, ...]
    survivors: tuple[str, ...]
    quests: tuple[QuestOutcome, ...]
    attitudes: tuple[tuple[str, str, str], ...]
    revealed: tuple[str, ...]
    ledger: tuple[str, ...]

    def lines(self) -> list[str]:
        out = [f"The campaign was called {self.title}."]
        for r in self.regions:
            out.append(_region_line(r))
        out.extend(f"{name} fell and did not return." for name in self.fallen)
        out.extend(f"{name} survived to the end." for name in self.survivors)
        out.extend(f"Quest {q.title}: {_quest_word(q.state)}." for q in self.quests)
        out.extend(
            f"{n} ({role}) ended {band} toward the party." for n, role, band in self.attitudes
        )
        out.extend(self.revealed)
        out.extend(self.ledger)
        return out


def _quest_word(state: QuestState) -> str:
    if state is QuestState.COMPLETED:
        return "completed"
    if state is QuestState.FAILED:
        return "failed"
    return "left unfinished"


def _region_line(region: RegionOutcome) -> str:
    if region.how is RegionResolution.DEFEAT:
        return f"In {region.region}, {region.boss} was defeated."
    if region.how is RegionResolution.ALLIANCE:
        return f"In {region.region}, {region.boss} was won over and joined the party."
    return f"{region.region} was never resolved."


def epilogue_facts(state: GameState) -> EpilogueFacts:
    campaign = state.campaign
    if campaign is None:
        raise ValueError("no campaign is installed")
    regions = tuple(
        RegionOutcome(r.name, r.boss.name, campaign.resolved.get(r.id))
        for r in campaign.plan.all_regions()
    )
    defeated_bosses = {r.boss.name for r in campaign.plan.all_regions() if boss_defeated(state, r)}
    pcs = [c for c in state.creatures.values() if c.pc is not None]
    npcs = [public_npc_view(n) for n in state.world.npcs.values()]
    revealed = tuple(f"{n.name} revealed: {s}" for n in npcs for s in n.revealed_secrets)
    return EpilogueFacts(
        title=campaign.plan.title,
        regions=regions,
        fallen=tuple(c.name for c in pcs if c.dead),
        survivors=tuple(c.name for c in pcs if not c.dead),
        quests=tuple(QuestOutcome(q.title, q.state) for q in state.world.quests.values()),
        attitudes=tuple(
            (n.name, n.role or "no stated role", n.attitude.value)
            for n in npcs
            if n.name not in defeated_bosses
        )[:MAX_ATTITUDES],
        revealed=revealed,
        ledger=tuple(f.text for f in state.world.facts[-MAX_LEDGER_FACTS:]),
    )


def _names(names: tuple[str, ...]) -> str:
    return ", ".join(names)


def _quest_lines(quests: tuple[QuestOutcome, ...]) -> list[str]:
    out: list[str] = []
    for label, wanted in (("Completed", {QuestState.COMPLETED}), ("Failed", {QuestState.FAILED})):
        titles = tuple(q.title for q in quests if q.state in wanted)
        if titles:
            out.append(f"{label} quests: {_names(titles)}.")
    open_titles = tuple(
        q.title for q in quests if q.state not in {QuestState.COMPLETED, QuestState.FAILED}
    )
    if open_titles:
        out.append(f"Left unfinished: {_names(open_titles)}.")
    return out


def template_epilogue(facts: EpilogueFacts) -> list[str]:
    lines = [f"The tale of {facts.title} is told."]
    lines.extend(_region_line(r) for r in facts.regions)
    if facts.fallen:
        lines.append(f"{_names(facts.fallen)} did not live to see the end.")
    if facts.survivors:
        lines.append(f"{_names(facts.survivors)} lived on.")
    lines.extend(_quest_lines(facts.quests))
    lines.extend(f"{n} ended {band} toward the party." for n, _, band in facts.attitudes)
    lines.extend(facts.revealed)
    lines.extend(facts.ledger)
    return lines
