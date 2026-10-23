"""M29.7c campaign plan repairs from the round-2 playtests (docs/playtests/M29_round2.md):
R11 one item per name and place, R10 a reward is never the quest's own item, R16 one person is
one record, R1 clear-step texts. The plans are the live model's, read from the round-2 save
fixtures; FakeLLM only, no network."""

from typing import Any

from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.entities import display_name
from aidm.models.campaign import CampaignPlan
from aidm.models.problem import Problem
from aidm.models.quests import StepKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.plan_repair import repair_plan
from aidm.rules.quest_items import act_quest_items
from aidm.rules.quest_plan import main_quest
from aidm.rules.quest_steps import step_met
from tests.ai.campaign_fixtures import draft_from_plan
from tests.session.playtest_saves import replay_until


def _plan(run: str) -> CampaignPlan:
    campaign = replay_until(run, 40).campaign
    assert campaign is not None
    return campaign.plan


def _repaired(run: str) -> tuple[CampaignPlan, list[Problem]]:
    notes: list[Problem] = []
    return repair_plan(_plan(run), notes), notes


def _named(items: list[Any], name: str) -> list[Any]:
    return [i for i in items if i.name.lower() == name.lower()]


def test_m29_one_item_per_name_and_place_p7_chime() -> None:
    """p7 332-333: the main route and The Master's Oath each hid an "unfinished chime" at
    Hollowbarrow Hall; now one chime lies there and both quests count it."""
    old = _plan("r2-p7")
    assert len(_named(act_quest_items(old, 2), "unfinished chime")) == 1  # runtime dedupe
    plan, notes = _repaired("r2-p7")
    chimes = _named(act_quest_items(plan, 2), "unfinished chime")
    assert [c.node_id for c in chimes] == ["hollowbarrow-hall"]
    assert any("one item, shared" in n.message and "unfinished chime" in n.message for n in notes)


def test_m29_shared_item_counts_for_every_quest() -> None:
    """The one chime, carried by a hero, meets both obtain steps; handed to the master it meets
    both deliver steps (and the obtain steps stay met)."""
    state = replay_until("r2-p7", 555)
    campaign = state.campaign
    assert campaign is not None
    side = next(q for q in campaign.plan.quests if q.id == "the-master-s-oath")
    route = main_quest(campaign.plan, 2).route("the-unfinished-chime")
    assert route is not None
    obtain, deliver = side.steps
    assert step_met(state, route.steps[0], "main-cairnhost-barrens")
    assert step_met(state, obtain, side.id)  # the main route's chime counts for the side quest
    hero = next(c for c in state.creatures.values() if c.pc is not None and c.pc.keepsakes)
    assert hero.pc is not None
    chime = next(k for k in hero.pc.keepsakes if k.name == "unfinished chime")
    hero.pc.keepsakes.remove(chime)
    state.world.npcs["boss-cairnhost-barrens"].keepsakes.append(chime)
    assert step_met(state, deliver, side.id)
    assert step_met(state, route.steps[1], "main-cairnhost-barrens")
    assert step_met(state, obtain, side.id)


def test_m29_shared_item_goes_to_one_person_p8_clapper() -> None:
    """p8 16, 18: the Cold Clapper lay twice in the chapel, one for the master and one for Sister
    Ondra; now one clapper, handed to the master, and Ondra is only shown it."""
    plan, notes = _repaired("r2-p8")
    assert len(_named(act_quest_items(plan, 1), "Cold Clapper")) == 1
    side = next(q for q in plan.quests if q.id == "the-cold-clapper")
    assert [s.kind for s in side.steps] == [StepKind.OBTAIN, StepKind.MEET]
    assert side.steps[1].npc == "sister-ondra"
    assert side.steps[1].text == "Meet Sister Ondra"  # M29.9b: the engine's line of a meet
    assert any("only shown it" in n.message for n in notes)


def test_m29_reward_is_never_the_quest_item() -> None:
    """p7 269-274 and the full run's plan: rewards that were the quest's own item."""
    p7, _ = _repaired("r2-p7")
    full, _ = _repaired("r2-full")
    for plan in (p7, full):
        for quest in plan.quests:
            own = {s.item.lower() for s in quest.steps if s.item}
            assert quest.reward_item is None or quest.reward_item.lower() not in own, quest.id
    coin = next(q for q in full.quests if q.id == "the-keeper-s-coin")
    assert coin.reward_item == "Mord Wexley's Token"
    ledger = next(q for q in p7.quests if q.id == "the-drowned-ledger")
    assert ledger.reward_item == "Wren Averntide's Token"


def test_m29_reward_name_keeps_its_apostrophe() -> None:
    """p7 274: the paid-out "tollmaster-s-ledger" showed as "Tollmaster S Ledger"."""
    assert display_name("tollmaster-s-ledger") == "Tollmaster's Ledger"
    assert display_name("mord-s-coin") == "Mord's Coin"
    assert display_name("chain-mail") == "Chain Mail"
    assert display_name("boots_of_speed") == "Boots Of Speed"


def test_m29_clear_step_text_names_what_the_place_fields() -> None:
    """p5 2, 243: "Snuff the bone-pyre the acolytes are stoking" at a copse of stirges and
    goblins; p4 202, 732: clear texts promising floods and severed bells."""
    plan, _ = _repaired("r2-p5")
    route = main_quest(plan, 1).route("douse-the-harvest-pyres")
    assert route is not None
    clear = route.steps[0]
    assert clear.kind is StepKind.CLEAR
    assert clear.text == "Win the fight at Gallowroot Copse"  # M29.9b T2: no themed foes
    p4, _ = _repaired("r2-p4")
    texts = [s.text for a in p4.acts for r in (a.main.routes if a.main else ()) for s in r.steps]
    assert not any("Flood" in t or "Sever" in t for t in texts)


def _assembled(draft: dict[str, Any]) -> tuple[CampaignPlan, list[Problem]]:
    notes: list[Problem] = []
    plan = assemble_plan(CampaignDraft.model_validate(draft), notes)
    assert isinstance(plan, CampaignPlan), plan
    return plan, notes


def test_m29_boss_and_npc_are_one_record_p4_dusk_oron() -> None:
    """p4 4, 1159, 1313: NPC "Dusk Oron" at the shrine and the shrine's master "Dusk Oron,
    Keeper of the Ledger" were two records; killing the master left the NPC greeting the party."""
    plan, notes = _assembled(draft_from_plan(_plan("r2-p4")))
    region = plan.acts[1].region
    boss_id = boss_npc_id(region)
    assert not any(n.name == "Dusk Oron" and n.id != boss_id for n in plan.npcs)
    assert any(n.id == boss_id for n in plan.npcs)
    assert any(boss_id in n.message and "one record" in n.message for n in notes)


def test_m29_same_name_head_elsewhere_stays_two_people() -> None:
    """A name head shared by someone who does NOT live at the master's lair is another person."""
    draft = draft_from_plan(_plan("r2-p4"))
    oron = next(n for n in draft["npcs"] if n["name"] == "Dusk Oron")
    oron["home_place"] = draft["acts"][1]["region"]["arrival"]["name"]
    plan, _ = _assembled(draft)
    assert any(n.name == "Dusk Oron" and n.id == "dusk-oron" for n in plan.npcs)


def test_m29_shared_item_is_owned_by_the_first_step() -> None:
    """The repaired p7 plan keeps every reference valid (it validates) and its act-2 items name
    the chime once, owned by the main route (the first step placing it)."""
    plan, _ = _repaired("r2-p7")
    chime = _named(act_quest_items(plan, 2), "unfinished chime")[0]
    assert chime.quest_id == "main-cairnhost-barrens"
