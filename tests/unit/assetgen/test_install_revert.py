"""Atomic install and revert (Addendum B.5 step 5, B.6): never overwrites, scores enforced."""

import json
from pathlib import Path

import pytest

from aidm.server.assetgen.install import LICENSE, load_manifest
from aidm.server.assetgen.review_cli import contact_sheet_main, install_main, revert_main
from aidm.server.assetgen.synthetic_png import synthetic_png
from tests.unit.assetgen.helpers import SENTINEL, make_repo, read_text_tree
from tests.unit.assetgen.imgs import noise_png
from tests.unit.scripts.helpers import load_script

PORTRAIT = "portrait.race.elf.f"
TOKEN = "monster_token.goblin"
GOOD = {"subject": 5, "style": 4, "composition": 4, "cleanliness": 5, "readability_64": 4}
MODEL = "gpt-image-1.5"


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        make_repo(root)
        self.base = root / "artifacts" / "assets"
        self.manifest = root / "aidm" / "web" / "static" / "assets" / "manifest.json"
        self.static = root / "aidm" / "web" / "static"
        self.lines: list[str] = []
        self.todo = load_script("gen_assets_todo")

    def after(self) -> None:
        self.todo.run(self.root, check=False)

    def stage(self) -> None:
        staging = self.base / "candidates"
        staging.mkdir(parents=True)
        (staging / f"{PORTRAIT}__c1.png").write_bytes(noise_png(600, 600, 5))
        one = {"keys": [PORTRAIT], "sheet": False, "model": MODEL, "prompt": "elf prompt"}
        (staging / f"{PORTRAIT}__c1.json").write_text(
            json.dumps({**one, "cost_eur": 0.12}), encoding="utf-8"
        )
        (staging / "sheet_a__c2.png").write_bytes(synthetic_png(512, 512, "s", sheet=True))
        sheet = {"keys": [TOKEN, "monster_token.bandit"], "sheet": True, "model": MODEL}
        (staging / "sheet_a__c2.json").write_text(
            json.dumps({**sheet, "prompt": "token sheet", "cost_eur": 0.3}), encoding="utf-8"
        )
        assert contact_sheet_main([], self.root, self.lines.append) == 0

    def review(self, rows: dict[str, dict[str, object]]) -> Path:
        path = self.base / "review_1.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def install(self, rows: dict[str, dict[str, object]]) -> int:
        review = self.review(rows)
        return install_main([str(review)], self.root, self.after, self.lines.append)

    def entry(self, key: str) -> dict[str, object]:
        return load_manifest(self.manifest)[key]


def _accept(**changes: object) -> dict[str, object]:
    return {**GOOD, "verdict": "accept", **changes}


def test_install_then_revert_round_trip(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.stage()
    todo_before = tmp_path / "ASSETS_TODO.md"
    assert repo.install({PORTRAIT: _accept(), TOKEN: _accept()}) == 0
    elf = repo.entry(PORTRAIT)
    target = repo.static / str(elf["file"])
    assert target.is_file() and not target.with_name(target.name + ".tmp").exists()
    assert elf["status"] == "real" and elf["source"] == f"generated:{MODEL}"
    assert elf["prompt"] == "elf prompt" and elf["license"] == LICENSE and elf["reviewed"] is True
    assert elf["cost_eur"] == 0.12
    assert list(elf)[:8] == [
        "kind",
        "file",
        "size",
        "transparent",
        "status",
        "prompt",
        "source",
        "license",
    ]
    assert repo.entry(TOKEN)["cost_eur"] == 0.15
    todo = (tmp_path / "ASSETS_TODO.md").read_text(encoding="utf-8")
    assert f"### {PORTRAIT}" not in todo and "### monster_token.bandit" in todo
    assert todo_before.exists()
    repo.lines.clear()
    assert revert_main([PORTRAIT], tmp_path, repo.after, repo.lines.append) == 0
    assert "before: status=real source=generated:" in repo.lines[0]
    assert "after:  status=placeholder" in repo.lines[1]
    assert not target.exists()
    back = repo.entry(PORTRAIT)
    assert back["status"] == "placeholder" and back["source"] == "" and "reviewed" not in back
    assert f"### {PORTRAIT}" in (tmp_path / "ASSETS_TODO.md").read_text(encoding="utf-8")


def test_install_refuses_a_score_below_four_and_non_accept_verdicts(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.stage()
    rows = {
        PORTRAIT: _accept(style=3),
        TOKEN: {**GOOD, "verdict": "retry", "prompt_fix": "less glow"},
    }
    assert repo.install(rows) == 1
    assert repo.entry(PORTRAIT)["status"] == "placeholder"
    assert repo.entry(TOKEN)["status"] == "placeholder"
    assert not (repo.static / "img" / "portraits" / "race_elf_f.png").exists()
    assert any("below 4" in line for line in repo.lines)


def test_install_refuses_a_missing_score(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.stage()
    row = _accept()
    del row["readability_64"]
    assert repo.install({PORTRAIT: row}) == 1
    assert repo.entry(PORTRAIT)["status"] == "placeholder"


def test_real_and_v1_entries_are_never_overwritten(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.stage()
    v1_key = "portrait.class.wizard"
    v1_file = repo.static / str(repo.entry(v1_key)["file"])
    v1_file.parent.mkdir(parents=True, exist_ok=True)
    v1_file.write_bytes(b"v1 original")
    index = json.loads((repo.base / "review_1.index.json").read_text(encoding="utf-8"))
    index["items"].append({**index["items"][0], "key": v1_key})
    (repo.base / "review_1.index.json").write_text(json.dumps(index), encoding="utf-8")
    before = repo.manifest.read_text(encoding="utf-8")
    assert repo.install({v1_key: _accept()}) == 1
    assert v1_file.read_bytes() == b"v1 original"
    assert repo.manifest.read_text(encoding="utf-8") == before
    assert any("real_entry" in line for line in repo.lines)


def test_an_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.stage()
    target = repo.static / str(repo.entry(PORTRAIT)["file"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"hand made")
    assert repo.install({PORTRAIT: _accept()}) == 1
    assert target.read_bytes() == b"hand made"
    assert repo.entry(PORTRAIT)["status"] == "placeholder"
    assert any("file_exists" in line for line in repo.lines)


def test_revert_refuses_v1_real_and_placeholder_entries(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    for key in ("portrait.class.wizard", PORTRAIT, "no.such.key"):
        assert revert_main([key], tmp_path, repo.after, repo.lines.append) == 1
    assert sum("revert refused" in line for line in repo.lines) == 3


def test_the_api_key_never_appears_in_pipeline_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IMAGE_API_KEY", SENTINEL)
    repo = Repo(tmp_path)
    repo.stage()
    repo.install({PORTRAIT: _accept()})
    revert_main([PORTRAIT], tmp_path, repo.after, repo.lines.append)
    assert SENTINEL not in "\n".join(repo.lines)
    assert SENTINEL not in read_text_tree(tmp_path)


def test_build_manifest_keeps_generated_metadata(tmp_path: Path) -> None:
    from aidm.server.asset_keys import derive_specs

    build = load_script("build_manifest")
    real_static = Path(__file__).resolve().parents[3] / "aidm" / "web" / "static"
    spec = next(s for s in derive_specs(real_static) if s.kind == "portrait" and not s.v1)
    old = {
        "source": f"generated:{MODEL}",
        "license": LICENSE,
        "prompt": "kept",
        "reviewed": True,
        "cost_eur": 0.12,
    }
    target = tmp_path / spec.file
    target.parent.mkdir(parents=True)
    target.write_bytes(noise_png(8, 8))
    entry = build.build_entry(spec, tmp_path, old)
    assert entry["status"] == "real" and entry["source"] == f"generated:{MODEL}"
    assert entry["license"] == LICENSE and entry["prompt"] == "kept"
    assert entry["reviewed"] is True and entry["cost_eur"] == 0.12
    assert list(entry)[-2:] == ["reviewed", "cost_eur"]
