"""M36.9 iteration 1: the chooser's `colour` field (the words that only describe how the hero does
the chosen steps; narration only, never an act), the rules that keep flourishes out of `other`,
zone targets that name who stands in them and shared target notes in the menu. FakeLLM only."""

from pathlib import Path

from aidm.dm.choice_tool import CHOOSE_TOOL, choice_tool
from aidm.dm.chooser import choose
from aidm.dm.chooser_menu import menu_lines
from aidm.dm.chooser_prompt import choose_system, shown_name, target_lines
from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.llm_types import tool_param
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import to_acts
from tests.ai.chooser_fixtures import GIFT_SEQ, QUESTS, REGS, TYPED, chooser_client, menu_at
from tests.ai.chooser_fixtures import state_at as at

HERO = "pc-p2"
INCENSE = "give:block-of-incense"
WIDOW = "widow-cabrelle"


def test_schema_requires_colour_as_a_plain_string() -> None:
    params = tool_param(choice_tool(menu_at(QUESTS, GIFT_SEQ, HERO)))["function"]["parameters"]
    assert params["required"] == ["steps", "other", "colour"]
    assert params["properties"]["colour"] == {"type": "string"}
    assert params["additionalProperties"] is False


async def test_colour_is_set_apart_from_the_steps(tmp_path: Path) -> None:
    state, menu = at(QUESTS, GIFT_SEQ), menu_at(QUESTS, GIFT_SEQ, HERO)
    step = {"do": INCENSE, "to": [WIDOW], "qty": None}
    reply = fake_tool_call(
        CHOOSE_TOOL, {"steps": [step], "other": None, "colour": "  with a deep bow "}
    )
    llm, _ = chooser_client(tmp_path, {CHOOSE_TOOL: [reply]})
    line = "I bow deeply and give the widow a block of incense"
    choice = await choose(state, HERO, line, menu, llm)
    assert isinstance(choice, MenuChoice)
    assert choice.colour == "with a deep bow" and not choice.other
    assert choice.steps == (MenuStep(entry=INCENSE, targets=(WIDOW,)),)


def test_colour_never_makes_an_act() -> None:
    state, menu = at(QUESTS, GIFT_SEQ), menu_at(QUESTS, GIFT_SEQ, HERO)
    steps = (MenuStep(entry=INCENSE, targets=(WIDOW,)),)
    line = "I kneel and give her the incense"
    plain = to_acts(state, menu, MenuChoice(steps=steps), REGS, line)
    coloured = to_acts(state, menu, MenuChoice(steps=steps, colour="I kneel"), REGS, line)
    assert coloured == plain and not any(isinstance(a, OtherIntent) for a in coloured)
    stunt = MenuChoice(steps=steps, other=True, other_text="juggle", colour="I kneel")
    others = [a for a in to_acts(state, menu, stunt, REGS, line) if isinstance(a, OtherIntent)]
    assert [o.text for o in others] == ["juggle"]


def test_rules_say_colour_other_and_the_step_limits() -> None:
    system = choose_system("player_input")
    for words in (
        "4. colour: the parts of the line that only describe HOW the hero does the chosen steps",
        "narration only, no mechanics",
        "never the manner, place or detail of a chosen step",
        "no unasked help_up, pay, search, travel, dash, hide or what_now",
        "Another hero's deed, or showing a carried item, is colour (not give)",
        "never a stand-in",  # M38.4: rule 1 (a named target is never swapped)
        "is the attack alone (it walks first)",
        "creeping up to strike first is offer:surprise",
        "a plea, offer, threat or bargain is offer:parley; only a question or greeting is talk",
        'item:restorative-draught>pc-p4, colour "kneel beside Elowen"',
        'talk>guard-1, colour "show the seal"',
    ):
        assert words in system, words


def test_zone_targets_name_who_stands_in_them() -> None:
    """m32-r5-typed 460 "I cast sleep on the zombie": the zombie stands in archway."""
    menu = menu_at("m32-r5-typed", 460, "pc-p6")
    labels = {t.id: t.label for t in menu.targets}
    assert labels["archway"] == "Leaning Gate (Zombie; Brienne), 25 ft"
    assert labels["deep_trees"] == "Old Pines (Elowen; Tamsin; Rook), here"
    assert labels["fallen_oak"] == "Toppled Trunk, 25 ft"
    zones = [line for line in target_lines(menu) if line.startswith("zone (25 ft)")]
    assert zones == [
        "zone (25 ft): game_trail, archway = Leaning Gate (Zombie; Brienne),"
        " fallen_oak = Toppled Trunk"
    ]


def test_shown_name_drops_a_name_the_id_already_says() -> None:
    assert shown_name("archway", "Archway (Zombie A)") == "archway (Zombie A)"
    assert shown_name("the-peddler", "The Peddler (trader)") == "the-peddler (trader)"
    assert shown_name("pool", "Glimmering Pool (Kobold A)") == "pool = Glimmering Pool (Kobold A)"
    assert shown_name("tunnel", "Tunnel") == "tunnel"


def test_neighbouring_targets_share_one_note() -> None:
    lines = menu_lines(menu_at(TYPED, 411, "pc-p8"))
    mace = next(line for line in lines if line.startswith("attack:mace "))
    assert mace.endswith("-> swarm-of-bats-1, kobold-1, kobold-2 (moves 30 ft first, 60%)")
    guidance = next(line for line in lines if line.startswith("cast:guidance "))
    assert guidance.endswith(
        "-> pc-p8, pc-p2, pc-p4, pc-p6; swarm-of-bats-1, kobold-1, kobold-2 (moves 30 ft first)"
    )
