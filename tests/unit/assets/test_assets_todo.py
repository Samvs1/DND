"""Style bible, manifest prompts and ASSETS_TODO.md (A2): fresh, complete, no banned terms."""

import json
import re
import shutil
from pathlib import Path

from aidm.server.asset_keys import AUDIO_KINDS, derive_specs
from aidm.server.asset_prompts import STYLE_BIBLE_PATH, build_prompt, load_style_bible
from tests.unit.scripts.helpers import load_script

todo = load_script("gen_assets_todo")
bm = load_script("build_manifest")
ROOT = todo.repo_root()
REAL_WEB = bm.default_web_root()
# Studios, games, films and brands that must never appear in a prompt or in the style bible.
DENYLIST = (
    r"baldur",
    r"\bbg3\b",
    r"larian",
    r"wizards of the coast",
    r"forgotten realms",
    r"dungeons (&|and) dragons",
    r"\bd&d\b",
    r"\bdnd\b",
    r"pathfinder",
    r"disney",
    r"pixar",
    r"ghibli",
    r"nintendo",
    r"zelda",
    r"pokemon",
    r"dark souls",
    r"witcher",
    r"skyrim",
    r"warcraft",
    r"tolkien",
    r"lord of the rings",
    r"star wars",
    r"marvel",
    r"final fantasy",
    r"diablo",
)


def _placeholders() -> dict[str, dict[str, object]]:
    manifest = todo.load_manifest(ROOT)
    return {k: v for k, v in manifest.items() if v["status"] == "placeholder"}


def test_committed_assets_todo_is_fresh() -> None:
    assert todo.run(ROOT, check=True) == 0


def test_todo_check_fails_when_stale_and_write_fixes_it(tmp_path: Path) -> None:
    root = tmp_path
    target = todo.manifest_file(root)
    target.parent.mkdir(parents=True)
    shutil.copy(todo.manifest_file(ROOT), target)
    assert todo.run(root, check=True) == 1  # no file yet
    assert todo.run(root, check=False) == 0
    assert todo.run(root, check=True) == 0
    todo.todo_file(root).write_text("# old\n", encoding="utf-8")
    assert todo.run(root, check=True) == 1
    data = json.loads(target.read_text(encoding="utf-8"))
    data["monster_token.goblin"]["status"] = "real"
    target.write_text(json.dumps(data), encoding="utf-8")
    todo.run(root, check=False)
    assert "### monster_token.goblin\n" not in todo.todo_file(root).read_text(encoding="utf-8")


def test_todo_lists_every_placeholder_with_path_size_transparency_and_prompt() -> None:
    text = todo.todo_file(ROOT).read_text(encoding="utf-8")
    placeholders = _placeholders()
    assert text.count("\n### ") == len(placeholders) > 0
    for key, entry in placeholders.items():
        assert f"\n### {key}\n- file: aidm/web/static/{entry['file']}\n" in text, key
    block = text.split("### monster_token.goblin\n", 1)[1].split("\n###", 1)[0]
    assert "- size: 256x256" in block and "- transparent: yes" in block and "- prompt: " in block


def test_every_placeholder_has_a_prompt_with_the_style_prefix() -> None:
    prefix = load_style_bible().prefix
    assert prefix.startswith("Retro 16-bit pixel art")
    for key, entry in _placeholders().items():
        prompt = str(entry["prompt"])
        assert prompt.strip(), key
        if entry["kind"] in AUDIO_KINDS:
            assert prompt.startswith("Audio brief"), key
            continue
        assert prompt.startswith(prefix), key
        size = entry["size"]
        assert isinstance(size, list), key
        width, height = size
        assert f"Target size {width}x{height}." in prompt, key
        assert ("Transparent background." in prompt) == bool(entry["transparent"]), key


def test_prompts_and_style_bible_contain_no_banned_terms() -> None:
    texts = [STYLE_BIBLE_PATH.read_text(encoding="utf-8")]
    texts += [str(e["prompt"]) for e in todo.load_manifest(ROOT).values()]
    texts.append(todo.todo_file(ROOT).read_text(encoding="utf-8"))
    for text in texts:
        for term in DENYLIST:
            assert re.search(term, text, re.I) is None, term


def test_prompts_carry_the_subject_details_from_data() -> None:
    specs = {s.key: s for s in derive_specs(REAL_WEB / "static")}

    def prompt(key: str) -> str:
        return build_prompt(specs[key])

    assert "Tiefling" in prompt("portrait.race.tiefling.f") and "female" in prompt(
        "portrait.race.tiefling.f"
    )
    assert "horns" in prompt("portrait.race.tiefling.m") and "male" in prompt(
        "portrait.race.tiefling.m"
    )
    goblin = prompt("monster_token.goblin")
    assert "Goblin" in goblin and "humanoid" in goblin and "challenge rating 0.25" in goblin
    assert "evocation" in prompt("spell_icon.fireball") and "flame" in prompt("spell_icon.fireball")
    assert "Blinded" in prompt("condition_icon.blinded")
    assert "cave" in prompt("zone_card.cave").lower() and "dusk" in prompt("region_banner.tier2")
    assert "tool" in prompt("item_icon.tool")
    assert "Wizard" in prompt("portrait.class.wizard")
    assert "Audio brief" in prompt("sfx.coin") and "pixel" not in prompt("sfx.coin")


def test_style_bible_has_the_required_sections() -> None:
    text = STYLE_BIBLE_PATH.read_text(encoding="utf-8").lower()
    for word in ("medium", "palette", "lighting", "framing", "line quality", "mood", "avoid"):
        assert word in text, word
    for kind in ("portrait", "monster_token", "item_icon", "spell_icon", "condition_icon"):
        assert f"`{kind}`" in text, kind
    assert {"zone_card", "region_banner"} <= set(load_style_bible().kinds)


def test_build_manifest_keeps_hand_prompts_and_refresh_rewrites_them(tmp_path: Path) -> None:
    web = tmp_path
    (web / "static").mkdir(parents=True)
    bm.run(web, check=False)
    path = bm.manifest_path(web)
    data = json.loads(path.read_text(encoding="utf-8"))
    generated = data["monster_token.goblin"]["prompt"]
    assert generated.startswith(load_style_bible().prefix)
    data["monster_token.goblin"]["prompt"] = "my own prompt"
    path.write_text(json.dumps(data), encoding="utf-8")
    bm.run(web, check=False)
    assert json.loads(path.read_text(encoding="utf-8"))["monster_token.goblin"]["prompt"] == (
        "my own prompt"
    )
    bm.run(web, check=False, refresh_prompts=True)
    assert (
        json.loads(path.read_text(encoding="utf-8"))["monster_token.goblin"]["prompt"] == generated
    )
