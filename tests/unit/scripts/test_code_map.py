"""scripts/code_map.py: import parsing and resolution, graph counts, families and the outputs."""

import ast
from pathlib import Path

from .helpers import load_script, write

cm = load_script("code_map")

KNOWN = {
    "aidm/models/state.py",
    "aidm/session/__init__.py",
    "aidm/session/combat_flow.py",
    "aidm/web/js/main.js",
    "aidm/web/js/ui/dom.js",
    "aidm/web/js/controller/typing.js",
}


def _graph(src: str, text: str) -> set[str]:
    _, _, imps = cm.parse(src, text)
    return cm.build_graph({src: imps, **{k: [] for k in KNOWN if k != src}})[src]


def test_from_package_import_module_names_the_module_not_the_package_init() -> None:
    text = "from aidm.session import combat_flow\nfrom aidm.models.state import GameState\n"
    assert _graph("aidm/dm/x.py", text) == {"aidm/session/combat_flow.py", "aidm/models/state.py"}


def test_imports_inside_functions_count() -> None:
    text = "def f():\n    import aidm.models.state\n"
    assert _graph("aidm/dm/x.py", text) == {"aidm/models/state.py"}


def test_a_stdlib_name_never_maps_to_a_same_named_js_file() -> None:
    assert _graph("aidm/dm/x.py", "import typing\nfrom collections.abc import Sequence\n") == set()


def test_js_relative_imports_static_side_effect_and_dynamic() -> None:
    src = "aidm/web/js/controller/typing.js"
    text = (
        "import { el } from '../ui/dom.js';\nimport '../main.js';\nconst m = import('../ui/dom');\n"
    )
    assert _graph(src, text) == {"aidm/web/js/ui/dom.js", "aidm/web/js/main.js"}


def test_graph_counts_importers_and_transitive_dependents() -> None:
    graph = cm.build_graph(
        {"a.py": [("b",)], "b.py": [("c",)], "c.py": [], "d.py": [("c",), ("b",)]}
    )
    back = cm.importers(graph)
    assert graph["d.py"] == {"b.py", "c.py"}
    assert back["c.py"] == {"b.py", "d.py"}
    assert cm.dependents(back, "c.py") == 3  # b and d directly, a through b
    assert cm.dependents(back, "a.py") == 0


def test_families_group_one_prefix_in_one_folder() -> None:
    paths = [f"aidm/dm/guard_{i}.py" for i in range(5)] + [
        "aidm/dm/guard.py",
        "aidm/rules/guard_x.py",
    ]
    assert cm.families(paths) == [("aidm/dm/guard*", sorted(paths[:6]))]
    assert cm.families(paths[:4]) == []


def test_summary_line_reads_docstring_or_header_comment() -> None:
    assert cm.summary_line("", ast.parse('"""The prose guard.\n\nMore."""\n')) == "The prose guard."
    assert (
        cm.summary_line("// Entry point: picks the mode.\nimport x;\n", None)
        == "Entry point: picks the mode."
    )
    assert cm.summary_line("", ast.parse("x = 1\n")) == ""
    assert cm.summary_line("const a = 1;\n", None) == ""


def test_main_writes_both_files(tmp_path: Path, monkeypatch) -> None:
    write(tmp_path, "aidm/models/state.py", '"""The state."""\n')
    write(tmp_path, "aidm/rules/dice.py", '"""Dice."""\nfrom aidm.models.state import X\n')
    write(tmp_path, "scripts/run.py", '"""Run."""\nimport aidm.rules.dice\n')
    monkeypatch.setattr(cm, "OUT", tmp_path / "out")
    assert cm.main(tmp_path) == 0
    index = (tmp_path / "out" / "INDEX.md").read_text(encoding="utf-8")
    assert "aidm/models/state.py | 1 | 1 | 0 | The state." in index
    assert "| aidm/models/state.py | 1 | 1 | 0 | 2 |" in (
        tmp_path / "out" / "CODEMAP.md"
    ).read_text(encoding="utf-8")
