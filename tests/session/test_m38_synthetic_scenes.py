"""M38.1: the synthetic scenes and scene rows of the interpretation eval (no network)."""

import json
from pathlib import Path

import pytest

from scripts.eval_interpret import main as eval_main
from scripts.interpret import lib
from scripts.interpret.corpus import Row, SceneRow, load_corpus
from scripts.interpret.evaluate import coverage
from scripts.interpret.synthetic import COVERS, REPLAYED, SCENES, scene

SEED = Path(__file__).resolve().parents[1] / "fixtures" / "interpret" / "synthetic.jsonl"


@pytest.mark.parametrize("name", sorted(SCENES))
def test_scene_builds_and_menu_builds_for_each_actor(name: str) -> None:
    built = scene(name)
    assert built.name == name and built.actors
    for actor in built.actors.values():
        assert actor in built.state.creatures
        assert lib.menu_for(built.state, actor).entries


def test_scene_copies_are_private() -> None:
    first = scene("village_explore")
    first.state.world.current_node = "nowhere-at-all"
    assert scene("village_explore").state.world.current_node != "nowhere-at-all"


def test_every_deleted_test_file_is_covered_by_a_scene_or_a_fixture_run() -> None:
    record = Path(__file__).resolve().parents[2] / "docs" / "next" / "m36_router_sentences.jsonl"
    files = {json.loads(x)["file"] for x in record.read_text("utf-8").splitlines() if x.strip()}
    mapped = {f for covered in COVERS.values() for f in covered}
    assert mapped | set(REPLAYED) == files
    assert not mapped & set(REPLAYED)
    assert set(COVERS) == set(SCENES)


def test_seed_rows_pass_offline_coverage() -> None:
    rows = load_corpus(SEED)
    assert len(rows) >= 5 and all(isinstance(r, SceneRow) for r in rows)
    assert {r.scene for r in rows if isinstance(r, SceneRow)} == set(SCENES)
    assert coverage(rows) == []
    assert eval_main(["--corpus", str(SEED)]) == 0


def test_malformed_scene_rows_are_reported(tmp_path: Path) -> None:
    good = json.loads(SEED.read_text("utf-8").splitlines()[0])
    unknown_scene = {**good, "id": "syn:x:1", "scene": "no_such_scene"}
    unknown_actor = {**good, "id": "syn:x:2", "actor_id": "pc-nobody"}
    bad_entry = {**good, "id": "syn:x:3"}
    bad_entry["expect"] = {"steps": [{"entry": "cast:not-a-spell"}]}
    rows: list[Row] = [
        SceneRow.model_validate(x) for x in (unknown_scene, unknown_actor, bad_entry)
    ]
    problems = coverage(rows)
    assert any("syn:x:1" in p and "no such" in p for p in problems)
    assert any("syn:x:2" in p and "not in the state" in p for p in problems)
    assert any("syn:x:3" in p and "cast:not-a-spell" in p for p in problems)
    broken = tmp_path / "broken.jsonl"
    broken.write_text(json.dumps({"id": "syn:x:4", "scene": "toll_offer"}) + "\n", encoding="utf-8")
    assert eval_main(["--corpus", str(broken)]) == 1
