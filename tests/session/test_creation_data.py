"""GET /api/creation-data: public wizard data that is sufficient to build a valid hero (M7.2)."""

from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from aidm.data.character_data import character_registries
from aidm.data.spell_defs import shipped_spell_ids
from aidm.models.abilities import Ability
from aidm.models.creation import AbilityMethod, CreationChoices
from aidm.rules.creation import validate_creation
from tests.session.server_fixtures import make_app

Json = dict[str, Any]
STANDARD = [15, 14, 13, 12, 10, 8]


def _fetch(tmp_path: Path) -> Json:
    with TestClient(make_app(tmp_path)) as client:
        response = client.get("/api/creation-data")
        assert response.status_code == 200
        return response.json()


def _free(options: list[str], taken: list[str], count: int) -> list[str]:
    return [o for o in options if o not in taken][:count]


def _choices(data: Json, race: Json, effective: Json, sub: str | None, cls: Json) -> Any:
    background = data["backgrounds"][0]
    taken = list(background["skills"]) + list(effective["skills"])
    class_skills = _free(cls["skill_choice"]["options"], taken, cls["skill_choice"]["choose"])
    race_pick = effective.get("skill_choice")
    race_skills = (
        _free(race_pick["options"], taken + class_skills, race_pick["choose"]) if race_pick else []
    )
    proficient = taken + class_skills + race_skills + cls["feature_skills"]
    feature_choices = {e["id"]: proficient[: e["choose"]] for e in cls["expertise"]}
    for pick in cls["feature_picks"] + effective["trait_picks"]:
        feature_choices[pick["id"]] = [o["id"] for o in pick["options"]][: pick["choose"]]
    tool = effective["tool_choice"]
    langs = [x["index"] for x in data["languages"] if x["index"] not in effective["languages"]]
    casting = cls["casting"]
    cantrips = casting["cantrips"][: casting["cantrip_count"]] if casting else []
    spells = casting["spells"][: casting["spell_count"]] if casting else []
    prepared = spells[:1] if casting and casting["spellbook"] else []
    if casting and casting["prepares"] and not casting["spellbook"]:
        prepared = casting["spells"][:1]
    abilities = list(Ability)
    race_cantrips: list[str] = []
    if effective["cantrip_choices"]:
        pool = data["race_cantrips"][effective["cantrip_class"]]
        race_cantrips = [c for c in pool if c not in cantrips][: effective["cantrip_choices"]]
    return CreationChoices(
        name="Tester",
        race=race["index"],
        subrace=sub,
        class_index=cls["index"],
        background=background["index"],
        ability_method=AbilityMethod.STANDARD_ARRAY,
        base_scores=dict(zip(abilities, STANDARD, strict=True)),
        ability_choice_picks=[
            Ability(a) for a in (effective.get("ability_choice") or {"options": []})["options"]
        ][: (effective.get("ability_choice") or {"choose": 0})["choose"]],
        class_skills=class_skills,
        race_skills=race_skills,
        tool_picks=tool["options"][: tool["choose"]] if tool else [],
        language_picks=langs[: effective["language_choices"]],
        equipment_picks={c["id"]: 0 for c in cls["equipment"]["choices"]},
        class_choices={
            c["id"]: [o["id"] for o in c["options"]][: c["choose"]] for c in cls["class_choices"]
        },
        feature_choices=feature_choices,
        cantrips=cantrips,
        race_cantrips=race_cantrips,
        spells=spells,
        prepared=prepared,
    )


def test_creation_data_shape_and_public_only(tmp_path: Path) -> None:
    data = _fetch(tmp_path)
    assert [c["index"] for c in data["classes"]] == [
        "fighter",
        "rogue",
        "wizard",
        "cleric",
        "ranger",
        "warlock",
    ]
    assert len(data["races"]) == 9 and len(data["backgrounds"]) >= 4
    assert data["portraits"] and all(p["key"].startswith("portrait.") for p in data["portraits"])
    text = str(data).lower()
    assert "api_key" not in text and "token" not in text


def test_creation_data_spells_are_shipped_only(tmp_path: Path) -> None:
    data = _fetch(tmp_path)
    shipped = shipped_spell_ids()
    assert data["spells"] and set(data["spells"]) <= shipped
    for cls in data["classes"]:
        casting = cls["casting"]
        if casting:
            assert set(casting["cantrips"] + casting["spells"]) <= shipped
    wizard = next(c for c in data["classes"] if c["index"] == "wizard")["casting"]
    assert wizard["spellbook"] and wizard["cantrip_count"] == 3 and wizard["spell_count"] == 6


def test_creation_data_builds_valid_hero_for_every_class_and_race(tmp_path: Path) -> None:
    data = _fetch(tmp_path)
    regs = character_registries()
    for cls in data["classes"]:
        for race in data["races"]:
            variants = [(None, race["effective"])] + [
                (s["index"], s["effective"]) for s in race["subraces"]
            ]
            for sub, effective in variants[-1:]:
                choices = _choices(data, race, effective, sub, cls)
                errors = validate_creation(choices, regs)
                assert errors == [], (cls["index"], race["index"], sub, errors)
