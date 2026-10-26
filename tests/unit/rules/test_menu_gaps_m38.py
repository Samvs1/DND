"""M38.2 menu gap: a spell with an attack roll aims at the people standing here, as a held weapon
does (M36.8c), on the real round-3 ferry state (Old Renn the ferryman stands by); M38.4: so does
a harmful spell with no attack roll (cause B)."""

from aidm.models.action_menu import ActionMenu, MenuEntry, MenuScope, MenuStep
from aidm.rules.acts import CastIntent, OfferStrikeIntent, PersonStrikeIntent
from aidm.rules.menu_casts import PERSON_NOTE, SCENE_NOTE
from aidm.rules.menu_steps import step_acts
from aidm.rules.spell_targets import deals_damage
from tests.ai.chooser_fixtures import REGS, menu_at, state_at

FERRY, RENN = ("r3-casters", 288), "old-renn-pitwater"
TOLL = ("m32-r5-typed", 61)


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry:
    return next(e for e in menu.entries if e.id == entry_id)


def _acts(at: tuple[str, int], actor: str, entry: str, *targets: str) -> list[object]:
    menu = menu_at(*at, actor)
    step = MenuStep(entry=entry, targets=targets)
    return list(step_acts(state_at(*at), menu, step, REGS))


def test_v1_m38_spell_attack_at_a_person_out_of_a_fight() -> None:
    """Router record "I cast fire bolt at Tobin": a person here is a target of Fire Bolt."""
    menu = menu_at(*FERRY, "pc-p2")
    bolt = _entry(menu, "cast:fire-bolt")
    assert menu.scope is MenuScope.EXPLORE and not bolt.starts_fight
    assert bolt.target_ids == (RENN,) and bolt.max_targets == 1
    assert bolt.option == "spell:fire-bolt" and bolt.note == PERSON_NOTE
    acts = _acts(FERRY, "pc-p2", "cast:fire-bolt", RENN)
    assert acts == [PersonStrikeIntent("pc-p2", RENN, "spell:fire-bolt")]


def test_spell_attack_entry_with_no_one_named_stays_the_scene_cast() -> None:
    acts = _acts(FERRY, "pc-p2", "cast:fire-bolt")
    assert acts == [CastIntent("pc-p2", "fire-bolt", (), at_scene=True)]


def test_v1_m38_harmful_spells_with_no_attack_roll_aim_at_a_person() -> None:
    """M38.4 cause B: "I cast burning hands at Merre", "Brienne casts magic missile at the
    ferryman" gave the bare scene cast; a spell that deals damage aims at the people here."""
    menu = menu_at(*FERRY, "pc-p2")
    for spell in ("magic-missile", "burning-hands", "thunderwave", "acid-splash"):
        entry = _entry(menu, f"cast:{spell}")
        assert entry.target_ids == (RENN,) and entry.note == PERSON_NOTE
        assert entry.option == f"spell:{spell}" and entry.max_targets == 1
        acts = _acts(FERRY, "pc-p2", f"cast:{spell}", RENN)
        assert acts == [PersonStrikeIntent("pc-p2", RENN, f"spell:{spell}")]
    cleric = _entry(menu_at(*FERRY, "pc-p4"), "cast:sacred-flame")
    assert cleric.target_ids == (RENN,) and cleric.option == "spell:sacred-flame"


def test_hostile_spells_that_deal_no_damage_stay_the_scene_cast() -> None:
    sleep = _entry(menu_at(*FERRY, "pc-p2"), "cast:sleep")
    charm = _entry(menu_at(*FERRY, "pc-p6"), "cast:charm-person")
    for entry in (sleep, charm):
        assert entry.target_ids == () and entry.note == SCENE_NOTE and entry.option is None


def test_spell_attack_at_a_bystander_while_foes_wait_is_a_person_strike() -> None:
    menu = menu_at(*TOLL, "pc-p6")
    bolt = _entry(menu, "cast:fire-bolt")
    assert menu.scope is MenuScope.OFFER and bolt.starts_fight
    assert bolt.target_ids == ("foe:thug", "reeve-hallick")
    person = _acts(TOLL, "pc-p6", "cast:fire-bolt", "reeve-hallick")
    assert person == [PersonStrikeIntent("pc-p6", "reeve-hallick", "spell:fire-bolt")]
    foe = _acts(TOLL, "pc-p6", "cast:fire-bolt", "foe:thug")
    assert foe and isinstance(foe[0], OfferStrikeIntent)
    assert _entry(menu, "cast:sleep").target_ids == ("foe:thug",)


def test_spell_strike_named_at_no_one_while_foes_wait_aims_at_the_foe() -> None:
    (strike,) = _acts(TOLL, "pc-p6", "cast:fire-bolt")
    assert isinstance(strike, OfferStrikeIntent) and strike.step is not None
    assert strike.step.targets == ("foe:thug",)


def test_golden_harmful_spells_deal_damage() -> None:
    """SRD 5.1 spell texts: Burning Hands (3d6 fire, DEX save), Magic Missile (1d4+1 force per
    dart), Sacred Flame (1d8 radiant, DEX save), Thunderwave (2d8 thunder, CON save), Fire Bolt
    (1d10 fire, attack) deal damage; Sleep (5d8 HP pool), Charm Person and Hold Person do not."""
    spells = REGS.spells
    harmful = ("burning-hands", "magic-missile", "sacred-flame", "thunderwave", "fire-bolt")
    for index in harmful:
        spell = spells.find(index)
        assert spell is not None and deals_damage(spell), index
    for index in ("sleep", "charm-person", "hold-person"):
        spell = spells.find(index)
        assert spell is not None and not deals_damage(spell), index
