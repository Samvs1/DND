"""The facts of a finished campaign and the deterministic epilogue built from them (SPEC 9).

The epilogue may only tell what actually happened, so its input is exactly these facts and
nothing else (no motives, no unrevealed secrets, no plan flavour): how each region was resolved
(defeat or alliance) and by which route the party finished (M23.9: by force, or the Peace
route; a finished Cunning route that helped; M29.9b T21: told by the engine's deeds of the
route's steps, never its title, and an ally "sided with the party": the roster stays the
heroes), the finale's question and the ending the party
chose (with the plan's ending text, public once chosen), who fell and who survived, how every
quest ended (completed, failed, left behind, let go, never taken up, left unfinished; M29.9b
T21: the main quests too), where each NPC's attitude ended (the public
band only), the secrets the party really learned, and every entry of the fact ledger.
`template_epilogue` is the safe fallback: it lists the same facts in plain past-tense sentences,
and a defeated boss is only ever "defeated". M29.5c G35: each boss's fate comes from the final
state (`RegionOutcome.fate`: an ally who later died, or one who turned on the party and lives,
is told so, and every boss gets an "At the end, X is dead/alive." fact). M32.1b X15: where the
tale began (the first act's arrival) and ended (where the party stands) come from the state
(`began`, `ended`; the guard checks the prose against them, `guard_epilogue.wrong_ends`).

Public API:
- `RegionOutcome`, `QuestOutcome`, `FinaleOutcome`, `EpilogueFacts` (frozen; `lines()` is the
  model's whole input).
- `epilogue_facts(state) -> EpilogueFacts` (ValueError without a campaign).
- `template_epilogue(facts) -> list[str]`: the deterministic fallback sentences: the story part
  (`epilogue_story`) and then the record (`epilogue_record`, M31.1c V20: who lived or fell, the
  main quests and every other quest by outcome, ENGINE-WRITTEN lines that follow the model's
  prose too, so the list is never left to the prose). A finale question left empty (it told an
  ally laid low, `aidm.dm.epilogue`) is not stated.
"""

from dataclasses import dataclass

from aidm.models.campaign import Act
from aidm.models.campaign_state import RegionResolution
from aidm.models.quests import QuestKind, RouteKind
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, Quest, QuestState
from aidm.rules.finale import chosen_ending
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.progression import boss_defeated, boss_npc
from aidm.rules.quest_plan import main_quest
from aidm.rules.scene import node_display_name
from aidm.rules.social import public_npc_view
from aidm.rules.step_text import state_names, step_deed

MAX_LEDGER_FACTS = 24
MAX_ATTITUDES = 10


@dataclass(frozen=True)
class RegionOutcome:
    region: str
    boss: str
    how: RegionResolution | None
    peace: str = ""  # M29.9b T21: the deeds of the finished Peace route ("met X, then ...")
    cunning: str = ""  # the deeds of the finished Cunning route
    fate: str = ""  # M29.5c G35: DEAD or TURNED from the final state ("" alive and as resolved)


DEAD = "dead"
TURNED = "turned"


@dataclass(frozen=True)
class QuestOutcome:
    title: str
    state: QuestState
    closed: ClosedReason | None = None
    main: bool = False


@dataclass(frozen=True)
class FinaleOutcome:
    question: str
    title: str
    text: str


@dataclass(frozen=True)
class EpilogueFacts:
    title: str
    regions: tuple[RegionOutcome, ...]
    finale: FinaleOutcome | None
    fallen: tuple[str, ...]
    survivors: tuple[str, ...]
    quests: tuple[QuestOutcome, ...]
    attitudes: tuple[tuple[str, str, str], ...]
    revealed: tuple[str, ...]
    ledger: tuple[str, ...]
    began: str = ""  # M32.1b X15: where the tale began and ended, from the state
    ended: str = ""

    def lines(self) -> list[str]:
        out = [f"The campaign was called {self.title}."]
        if self.began and self.ended:
            out.append(f"The tale began at {self.began} and ended at {self.ended}.")
        for r in self.regions:
            out.append(_region_line(r))
        out.extend(_fate_line(r) for r in self.regions)
        if self.finale is not None:
            if self.finale.question:
                out.append(f"The final choice: {self.finale.question}")
            out.append(f"The party chose: {self.finale.title}. {self.finale.text}")
        out.extend(f"{name} fell and did not return." for name in self.fallen)
        out.extend(f"{name} survived to the end." for name in self.survivors)
        out.extend(f"Quest {q.title}: {_quest_word(q)}." for q in self.quests)
        out.extend(
            f"{n} ({role}) ended {band} toward the party." for n, role, band in self.attitudes
        )
        out.extend(self.revealed)
        out.extend(self.ledger)
        return out


_CLOSED_WORDS = {ClosedReason.LEFT_BEHIND: "left behind", ClosedReason.WITHDRAWN: "let go"}
_STATE_WORDS = {
    QuestState.COMPLETED: "completed",
    QuestState.FAILED: "failed",
    QuestState.OFFERED: "never taken up",
}


def _quest_word(quest: QuestOutcome) -> str:
    if quest.closed is not None:
        return _CLOSED_WORDS[quest.closed]
    return _STATE_WORDS.get(quest.state, "left unfinished")


def _region_line(region: RegionOutcome) -> str:
    if region.how is RegionResolution.DEFEAT:
        helped = (
            f" Cunning paved the way first: the party {region.cunning}." if region.cunning else ""
        )
        return f"In {region.region}, {region.boss} was defeated by force.{helped}"
    if region.how is RegionResolution.ALLIANCE:
        way = f", after the party {region.peace}" if region.peace else ""
        if region.fate == DEAD:
            return (
                f"In {region.region}, {region.boss} was won over{way}, but later died in a fight."
            )
        if region.fate == TURNED:
            return (
                f"In {region.region}, {region.boss} was won over{way}, but turned on the party at"
                " the last and still lives."
            )
        return f"In {region.region}, {region.boss} was won over and sided with the party{way}."
    if region.fate == DEAD:
        return f"In {region.region}, {region.boss} was slain."
    return f"{region.region} was never resolved."


def _fate_line(region: RegionOutcome) -> str:
    """M29.5c G35: the boss's fate from the final state, stated plainly (the epilogue told a
    living boss as fallen and a dead one keeping his word)."""
    if region.fate == DEAD:
        return f"At the end, {region.boss} is dead."
    return f"At the end, {region.boss} is alive."


def _fate(state: GameState, act: Act) -> str:
    npc = boss_npc(state, act.region)
    if boss_defeated(state, act.region) or (npc is not None and npc.dead):
        return DEAD
    return TURNED if npc is not None and npc.hostile else ""


def _finished_route(state: GameState, act: Act, kind: RouteKind) -> str:
    """What the party did on the act's main-quest route of `kind` it finished (M29.9b T21: the
    engine's deeds of its steps, never the model's route title), else ""."""
    campaign = state.campaign
    known = state.world.quests.get(main_quest_id(act.region))
    if campaign is None or known is None:
        return ""
    for route in main_quest(campaign.plan, act.index).routes:
        progress = known.route(route.id)
        if route.kind is kind and progress is not None and progress.steps_done >= len(route.steps):
            names = state_names(state)
            return ", then ".join(step_deed(s, names) for s in route.steps)
    return ""


def _region_outcome(state: GameState, act: Act) -> RegionOutcome:
    campaign = state.campaign
    how = campaign.resolved.get(act.region.id) if campaign is not None else None
    return RegionOutcome(
        act.region.name,
        act.region.boss.name,
        how,
        peace=_finished_route(state, act, RouteKind.PEACE),
        cunning=_finished_route(state, act, RouteKind.CUNNING),
        fate=_fate(state, act),
    )


def _finale_outcome(state: GameState) -> FinaleOutcome | None:
    campaign = state.campaign
    ending = chosen_ending(state)
    finale = campaign.plan.finale if campaign is not None else None
    if finale is None or ending is None:
        return None
    return FinaleOutcome(finale.question, ending.title, ending.text)


def _quest_outcome(quest: Quest) -> QuestOutcome:
    main = quest.kind is QuestKind.MAIN
    return QuestOutcome(quest.title, quest.state, quest.closed_reason, main=main)


def _quests(state: GameState) -> tuple[QuestOutcome, ...]:
    """M29.9b T21: every quest, the main quests first (they were missing from "Completed")."""
    quests = sorted(state.world.quests.values(), key=lambda q: q.kind is not QuestKind.MAIN)
    return tuple(_quest_outcome(q) for q in quests)


def epilogue_facts(state: GameState) -> EpilogueFacts:
    campaign = state.campaign
    if campaign is None:
        raise ValueError("no campaign is installed")
    regions = tuple(_region_outcome(state, act) for act in campaign.plan.acts)
    defeated_bosses = {r.boss.name for r in campaign.plan.all_regions() if boss_defeated(state, r)}
    pcs = [c for c in state.creatures.values() if c.pc is not None]
    npcs = [public_npc_view(n) for n in state.world.npcs.values()]
    revealed = tuple(f"{n.name} revealed: {s}" for n in npcs for s in n.revealed_secrets)
    return EpilogueFacts(
        title=campaign.plan.title,
        regions=regions,
        finale=_finale_outcome(state),
        fallen=tuple(c.name for c in pcs if c.dead),
        survivors=tuple(c.name for c in pcs if not c.dead),
        quests=_quests(state),
        attitudes=tuple(
            (n.name, n.role or "no stated role", n.attitude.value)
            for n in npcs
            if n.name not in defeated_bosses
        )[:MAX_ATTITUDES],
        revealed=revealed,
        ledger=tuple(f.text for f in state.world.facts[-MAX_LEDGER_FACTS:]),
        began=node_display_name(state, campaign.plan.acts[0].region.arrival.id)
        if campaign.plan.acts
        else "",
        ended=node_display_name(state, state.world.current_node),
    )


def _names(names: tuple[str, ...]) -> str:
    return ", ".join(names)


_QUEST_LABELS = (
    ("completed", "Completed quests"),
    ("failed", "Failed quests"),
    ("left behind", "Left behind"),
    ("let go", "Favours let go"),
    ("never taken up", "Never taken up"),
    ("left unfinished", "Left unfinished"),
)


def _quest_lines(quests: tuple[QuestOutcome, ...]) -> list[str]:
    mains = [f"{q.title} ({_quest_word(q)})" for q in quests if q.main]
    out = [f"Main quests: {', '.join(mains)}."] if mains else []
    for word, label in _QUEST_LABELS:
        titles = tuple(q.title for q in quests if not q.main and _quest_word(q) == word)
        if titles:
            out.append(f"{label}: {_names(titles)}.")
    return out


def epilogue_record(facts: EpilogueFacts) -> list[str]:
    """M31.1c V20: the engine-written close of every epilogue: who lived, who fell, the quests."""
    lines: list[str] = []
    if facts.fallen:
        lines.append(f"{_names(facts.fallen)} did not live to see the end.")
    if facts.survivors:
        lines.append(f"{_names(facts.survivors)} lived on.")
    return lines + _quest_lines(facts.quests)


def epilogue_story(facts: EpilogueFacts) -> list[str]:
    """The template's story part: the regions, the finale, the people, the ledger."""
    lines = [f"The tale of {facts.title} is told."]
    lines.extend(_region_line(r) for r in facts.regions)
    if facts.finale is not None:
        if facts.finale.question:
            lines.append(f"At the last, the party faced a choice: {facts.finale.question}")
        lines.append(f"They chose: {facts.finale.title}. {facts.finale.text}")
    lines.extend(f"{n} ended {band} toward the party." for n, _, band in facts.attitudes)
    lines.extend(facts.revealed)
    lines.extend(facts.ledger)
    return lines


def template_epilogue(facts: EpilogueFacts) -> list[str]:
    return epilogue_story(facts) + epilogue_record(facts)
