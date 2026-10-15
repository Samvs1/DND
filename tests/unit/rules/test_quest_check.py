"""M23.6 quest checks a generated plan must pass: uncompletable steps and routes are Problems."""

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan, QuestPlan
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.quest_check import check_plan_quests, learnable_words


def _with_steps(plan: CampaignPlan, quest_id: str, *steps: QuestStep) -> CampaignPlan:
    quests: list[QuestPlan] = [
        q.model_copy(update={"steps": steps}) if q.id == quest_id else q for q in plan.quests
    ]
    return plan.model_copy(update={"quests": tuple(quests)})


def test_clear_of_the_arrival_is_a_problem() -> None:
    plan = load_sample_campaign()
    arrival = plan.acts[0].region.arrival.id
    step = QuestStep(kind=StepKind.CLEAR, text="Clear the quay", nodes=(arrival,))
    codes = [p.code for p in check_plan_quests(_with_steps(plan, "missing-ledger", step))]
    assert codes == ["step_clear_arrival"]


def test_learn_tag_must_be_learnable_in_its_act() -> None:
    plan = load_sample_campaign()
    words = learnable_words(plan, plan.acts[0])
    assert {"saltcellar", "ledger", "gullmere"} <= words and "cistern" not in words
    good = QuestStep(kind=StepKind.LEARN, text="Learn of the tunnels", tag="saltcellar")
    assert check_plan_quests(_with_steps(plan, "missing-ledger", good)) == []
    far = QuestStep(kind=StepKind.LEARN, text="Learn of the cistern", tag="cistern")
    codes = [p.code for p in check_plan_quests(_with_steps(plan, "missing-ledger", far))]
    assert codes == ["step_tag"]


def test_deliver_counts_only_items_obtained_by_the_same_quest() -> None:
    plan = load_sample_campaign()
    peace = plan.acts[0].main.routes[0] if plan.acts[0].main is not None else None
    assert peace is not None
    item = peace.steps[0].item
    deliver = QuestStep(kind=StepKind.DELIVER, text="Hand it over", item=item, npc="tobin-marrow")
    bad = _with_steps(plan, "missing-ledger", deliver)
    assert [p.code for p in check_plan_quests(bad)] == ["deliver_item"]


def test_peace_route_needs_a_boss_ally_path() -> None:
    plan = load_sample_campaign()
    act = plan.acts[2]
    boss = act.region.boss.model_copy(update={"ally_path": None})
    region = act.region.model_copy(update={"boss": boss})
    acts = (*plan.acts[:2], act.model_copy(update={"region": region}))
    codes = [p.code for p in check_plan_quests(plan.model_copy(update={"acts": acts}))]
    assert codes == ["route_peace_ally"]
