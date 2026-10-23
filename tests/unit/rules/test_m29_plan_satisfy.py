"""M29.9b closed world at plan time (rules/plan_satisfy.py) and engine-written step lines
(rules/step_text.py, docs/playtests/M29_round3.md T2 T3 T14)."""

from aidm.models.campaign import CampaignPlan, QuestPlan
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.plan_repair import repair_plan
from aidm.rules.plan_satisfy import satisfy_plan, unsatisfiable
from aidm.rules.quest_items import act_quest_items
from aidm.rules.step_text import StepNames, plan_names, step_deed, step_text
from tests.session.playtest_saves import replay_until
from tests.session.progression_fixtures import plan

NAMES = StepNames(
    {"weeping-bastion": "Weeping Bastion", "fogward-gallows": "Fogward Gallows"},
    {"old-renn": "Old Renn", "ulva": "Ulva", "rutter": "Rutter the Gap"},
)


def _step(kind: StepKind, **fields: object) -> QuestStep:
    return QuestStep.model_validate({"kind": kind, "text": "model words", **fields})


def test_m29_step_lines_come_from_the_checked_fields() -> None:
    cases = [
        (_step(StepKind.VISIT, nodes=("weeping-bastion",)), "Go to Weeping Bastion"),
        (
            _step(StepKind.VISIT, nodes=("fogward-gallows", "weeping-bastion")),
            "Go to Fogward Gallows and Weeping Bastion",
        ),
        (_step(StepKind.CLEAR, nodes=("weeping-bastion",)), "Win the fight at Weeping Bastion"),
        (_step(StepKind.DEFEAT, npc="ulva"), "Defeat Ulva"),
        (
            _step(StepKind.OBTAIN, item="Drowned Lockbox", nodes=("fogward-gallows",)),
            "Find the Drowned Lockbox at Fogward Gallows",
        ),
        (
            _step(StepKind.OBTAIN, item="Heat-Crystal", nodes=("weeping-bastion",), count=3),
            "Find 3 x Heat-Crystal at Weeping Bastion",
        ),
        (
            _step(StepKind.DELIVER, item="Sorrel's Spring-Map", npc="old-renn"),
            "Give Sorrel's Spring-Map to Old Renn",
        ),
        (_step(StepKind.MEET, npc="old-renn"), "Meet Old Renn"),
        (_step(StepKind.WIN_OVER, npc="ulva", band=AttitudeBand.ALLY), "Make Ulva an ally"),
        (_step(StepKind.LEARN, tag="blackpine"), "Learn about blackpine"),
        (
            _step(StepKind.LEARN, tag="thaw", item="Notes on Thaw", nodes=("weeping-bastion",)),
            "Learn about thaw from the Notes on Thaw",
        ),
        (_step(StepKind.PAY, npc="rutter", gold=4), "Pay Rutter the Gap 4 gold"),
        (_step(StepKind.FREE), "model words"),
    ]
    for step, line in cases:
        assert step_text(step, NAMES) == line
    clear = _step(StepKind.CLEAR, nodes=("weeping-bastion",))
    assert step_deed(clear, NAMES) == "won the fight at Weeping Bastion"


def _with_quest(base: CampaignPlan, *steps: QuestStep) -> CampaignPlan:
    """The sample plan with its first side quest's steps replaced (owner `missing-ledger`)."""
    quests = list(base.quests)
    quests[0] = quests[0].model_copy(update={"steps": steps})
    return base.model_copy(update={"quests": tuple(quests)})


def _codes(p: CampaignPlan) -> list[str]:
    return [problem.code for problem in unsatisfiable(p)]


def _ledger(p: CampaignPlan) -> QuestPlan:
    return next(q for q in p.quests if q.id == "missing-ledger")


def test_m29_unsatisfiable_learn_tag_gets_a_clue() -> None:
    p = _with_quest(plan(), _step(StepKind.LEARN, tag="dragon"))
    assert _codes(p) == ["learn_source"]
    fixed = satisfy_plan(p, notes := [])
    clue = _ledger(fixed).steps[0]
    assert (clue.item, clue.nodes) == ("Notes on Dragon", ("rotting-boathouse",))
    assert _codes(fixed) == [] and notes
    placed = [i for i in act_quest_items(fixed, 1) if i.name == "Notes on Dragon"]
    assert [(i.node_id, i.teaches, i.quest_id) for i in placed] == [
        ("rotting-boathouse", "dragon", "missing-ledger")
    ]


def test_m29_unsatisfiable_give_gets_its_item_placed() -> None:
    p = _with_quest(plan(), _step(StepKind.DELIVER, item="Lost Ring", npc="tobin-marrow"))
    assert _codes(p) == ["give_item"]
    fixed = satisfy_plan(p, [])
    kinds = [s.kind for s in _ledger(fixed).steps]
    assert kinds == [StepKind.OBTAIN, StepKind.DELIVER] and _codes(fixed) == []


def test_m29_unsatisfiable_person_becomes_the_giver() -> None:
    p = _with_quest(plan(), _step(StepKind.MEET, npc="piper-nobody"))
    assert _codes(p) == ["step_person"]
    fixed = satisfy_plan(p, [])
    assert _ledger(fixed).steps[0].npc == "tobin-marrow" and _codes(fixed) == []
    gone = _with_quest(plan(), _step(StepKind.DEFEAT, npc="piper-nobody"))
    assert _ledger(satisfy_plan(gone, [])).steps[0].kind is StepKind.FREE


def test_m29_unsatisfiable_place_is_dropped() -> None:
    p = _with_quest(plan(), _step(StepKind.VISIT, nodes=("rotting-boathouse", "dark-lantern-room")))
    assert _codes(p) == ["step_place"]
    fixed = satisfy_plan(p, [])
    assert _ledger(fixed).steps[0].nodes == ("rotting-boathouse",) and _codes(fixed) == []


def test_m29_round_three_plans_are_satisfiable() -> None:
    """The three round-3 plans: every step can be finished before and after the repairs."""
    for run in ("r3-full", "r3-items", "r3-casters"):
        state = replay_until(run, 40)
        assert state.campaign is not None
        raw = state.campaign.plan
        assert unsatisfiable(raw) == [], run
        assert unsatisfiable(repair_plan(raw, [])) == [], run


def test_m29_side_quests_never_meet_a_master_nor_visit_the_givers_home() -> None:
    names = plan_names(plan())
    assert names.person("boss-gullmere-quay") == "Gorran Hookhand"
    for run in ("r3-full", "r3-items", "r3-casters"):
        state = replay_until(run, 40)
        assert state.campaign is not None
        fixed = repair_plan(state.campaign.plan, [])
        homes = {n.id: n.home_node for n in fixed.npcs}
        masters = {f"boss-{r.id}" for r in fixed.all_regions()}
        for quest in fixed.quests:
            for step in quest.steps:
                assert not (step.kind is StepKind.MEET and step.npc in masters), quest.id
                home = homes.get(quest.giver_npc_id)
                assert not (step.kind is StepKind.VISIT and home in step.nodes), quest.id
