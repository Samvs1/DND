"""scripts/code_map.py: import resolution, the graph counts and the families (no mapify run)."""

from .helpers import load_script

cm = load_script("code_map")

KNOWN = {
    "aidm/models/state.py",
    "aidm/dm/__init__.py",
    "aidm/dm/guard.py",
    "aidm/web/js/main.js",
    "aidm/web/js/ui/dom.js",
    "aidm/web/js/controller/typing.js",
}


def test_resolve_dotted_python_module_and_package() -> None:
    assert cm.resolve("aidm/dm/guard.py", "aidm.models.state", KNOWN) == "aidm/models/state.py"
    assert cm.resolve("aidm/dm/guard.py", "aidm.dm", KNOWN) == "aidm/dm/__init__.py"


def test_resolve_never_maps_a_stdlib_name_to_a_same_named_js_file() -> None:
    # mapify's own graph maps `import typing` to controller/typing.js
    assert cm.resolve("aidm/dm/guard.py", "typing", KNOWN) is None
    assert cm.resolve("aidm/dm/guard.py", "collections.abc", KNOWN) is None


def test_resolve_relative_js_paths() -> None:
    assert cm.resolve("aidm/web/js/main.js", "./ui/dom.js", KNOWN) == "aidm/web/js/ui/dom.js"
    src = "aidm/web/js/controller/typing.js"
    assert cm.resolve(src, "../ui/dom.js", KNOWN) == "aidm/web/js/ui/dom.js"
    assert cm.resolve(src, "../ui/dom", KNOWN) == "aidm/web/js/ui/dom.js"


def test_graph_counts_importers_and_transitive_dependents() -> None:
    graph = cm.build_graph({"a.py": ["b"], "b.py": ["c"], "c.py": [], "d.py": ["c", "b"]})
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
    assert cm.summary_line('"""The prose guard.\n\nMore."""\n', ".py") == "The prose guard."
    assert (
        cm.summary_line("// Entry point: picks the mode.\nimport x;\n", ".js")
        == "Entry point: picks the mode."
    )
    assert cm.summary_line("x = 1\n", ".py") == ""
    assert cm.summary_line("const a = 1;\n", ".js") == ""
