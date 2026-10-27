"""Contract rule B6 (a leveled spell spends a slot and uses its caster's DC) on real saves."""

from aidm.models.events import CheckResolved
from scripts.contractlib.save import Save
from scripts.contractlib.spell_rules import SpellPaths
from tests.unit.contract.helpers import fixture, rules, run


def test_contract_b6_slot_spent_and_caster_dc_pass() -> None:
    """m39-r7-quests: 22 casts, magic missile and guiding bolt each spend a level-1 slot."""
    assert rules(run(fixture("m39-r7-quests"), SpellPaths()), "B6") == []


def test_contract_b6_a_cast_without_its_slot_is_found() -> None:
    """m39-r7-quests 392: pc-p8 casts magic missile at level 1; its slot event (391) is left out."""
    save = fixture("m39-r7-quests")
    events = [e for e in save.events if e.seq != 391]
    found = rules(run(Save(save.name, save.folder, save.initial, events), SpellPaths()), "B6")
    assert [f.idx for f in found] == [392] and "magic-missile" in found[0].reason


def test_contract_b6_a_scroll_and_a_racial_spell_need_no_slot() -> None:
    """m29-r2-p4 1145 (a scroll read) and m29-r3-full 1450 (darkness from a racial use)."""
    assert rules(run(fixture("m29-r2-p4"), SpellPaths()), "B6") == []
    assert rules(run(fixture("m29-r3-full"), SpellPaths()), "B6") == []


def test_contract_b6_a_save_with_the_wrong_dc_is_found() -> None:
    """m39-r7-quests: the sacred flame save (real event) with its DC raised by one."""
    save = fixture("m39-r7-quests")
    events = list(save.events)
    at = next(
        i
        for i, e in enumerate(events)
        if isinstance(e.event, CheckResolved)
        and e.event.source_id
        and e.event.result.kind == "save"
    )
    real = events[at].event
    assert isinstance(real, CheckResolved)
    wrong = real.model_copy(
        update={"result": real.result.model_copy(update={"dc": real.result.dc + 1})}
    )
    events[at] = events[at].model_copy(update={"event": wrong})
    found = rules(run(Save(save.name, save.folder, save.initial, events), SpellPaths()), "B6")
    assert [f.idx for f in found] == [events[at].seq] and "DC" in found[0].reason
