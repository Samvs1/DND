"""The code map (owner 2026-10-27): what each file is for, who imports it, and the hub files.

  python scripts/code_map.py            scan with mapifyy-cli (about 70 s), then write the map
  python scripts/code_map.py --no-scan  rebuild the map from the last scan

mapifyy-cli (dev extra, pinned) parses every .py and .js file with tree-sitter into
artifacts/codemap/mapify/codebase_blueprint.json (classes, functions, import strings per file).
Its own graph and "God Nodes" are not used: it links calls by bare name (every `.get` points at
one `get` function) and maps `import typing` to typing.js. This script resolves the import
strings itself (dotted Python modules, relative JS paths) over aidm/ and scripts/ (tests are not
coupling) and writes, under artifacts/codemap/ (gitignored):
- CODEMAP.md: lines per folder, the hubs (imported by many AND importing many: fan-in x fan-out),
  the most imported files, the files near the 400-line limit, and file families (one name
  prefix, many files in one folder);
- INDEX.md: one line per file: path, lines, imported by, imports, the first line of its docstring
  or header comment. Grep it to find where a concept lives before opening files.
"""

import ast
import io
import json
import os
import posixpath
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "codemap"
BLUEPRINT = OUT / "mapify" / "codebase_blueprint.json"
CODE_DIRS = ("aidm/", "scripts/")
LINE_LIMIT, NEAR_LIMIT, FAMILY_MIN, TOP = 400, 340, 6, 20

Graph = dict[str, set[str]]


def scan() -> None:
    """Run mapifyy-cli in a child process (its rich console output is captured, not printed)."""
    cmd = [sys.executable, "-c", "from mapify.cli import main; main()", "run", str(ROOT)]
    cmd += ["--output", str(BLUEPRINT)]
    env = os.environ | {"PYTHONIOENCODING": "utf-8"}  # its emoji crash a cp1252 console
    done = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace", env=env, check=False
    )
    if done.returncode != 0:
        tail = "\n".join(done.stderr.splitlines()[-5:])
        raise SystemExit(f"code map: mapify failed (pip install -e .[dev]?)\n{tail}")


def load_imports(blueprint: Path) -> dict[str, list[str]]:
    files = json.loads(blueprint.read_text(encoding="utf-8"))["files"]
    out = {Path(rel).as_posix(): list(info["imports"]) for rel, info in files.items()}
    return {rel: imps for rel, imps in out.items() if rel.startswith(CODE_DIRS)}


def resolve(src: str, imp: str, known: set[str]) -> str | None:
    """The file an import string names, or None (stdlib, third party, unknown)."""
    if imp.startswith("."):
        path = posixpath.normpath(posixpath.join(posixpath.dirname(src), imp))
        candidates = [path, f"{path}.js"]
    else:
        base = imp.replace(".", "/")
        candidates = [f"{base}.py", f"{base}/__init__.py"]
    return next((c for c in candidates if c in known and c != src), None)


def build_graph(imports: dict[str, list[str]]) -> Graph:
    known = set(imports)
    graph: Graph = {src: set() for src in imports}
    for src, imps in imports.items():
        graph[src] |= {dst for imp in imps if (dst := resolve(src, imp, known))}
    return graph


def importers(graph: Graph) -> Graph:
    back: Graph = {node: set() for node in graph}
    for src, dsts in graph.items():
        for dst in dsts:
            back[dst].add(src)
    return back


def dependents(back: Graph, node: str) -> int:
    """How many files depend on `node` directly or through others (its blast radius)."""
    seen, todo = {node}, [node]
    while todo:
        for nxt in back[todo.pop()] - seen:
            seen.add(nxt)
            todo.append(nxt)
    return len(seen) - 1


def families(paths: list[str]) -> list[tuple[str, list[str]]]:
    """Files in one folder sharing a name prefix ("aidm/dm/guard*": guard.py, guard_alive.py)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        folder, name = posixpath.split(path)
        groups[f"{folder}/{name.split('.')[0].split('_')[0]}*"].append(path)
    found = [
        (key, sorted(members)) for key, members in groups.items() if len(members) >= FAMILY_MIN
    ]
    return sorted(found, key=lambda kv: -len(kv[1]))


def summary_line(text: str, suffix: str) -> str:
    if suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(text)) or ""
        except SyntaxError:
            doc = ""
        return doc.strip().splitlines()[0] if doc.strip() else ""
    head = text.lstrip().splitlines()[:1]
    return (
        head[0].lstrip("/* ").strip() if head and head[0].lstrip().startswith(("//", "/*")) else ""
    )


def read_files(paths: list[str]) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    for rel in paths:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        out[rel] = (len(text.splitlines()), summary_line(text, Path(rel).suffix))
    return out


def table(head: str, rows: list[list[str]]) -> list[str]:
    cols = head.count("|") - 1
    return [head, "|" + "---|" * cols] + ["| " + " | ".join(row) + " |" for row in rows]


def codemap_lines(graph: Graph, info: dict[str, tuple[int, str]]) -> list[str]:
    back = importers(graph)
    lines_of = {p: info[p][0] for p in graph}
    folders: Counter[str] = Counter()
    counts: Counter[str] = Counter(posixpath.dirname(p) for p in graph)
    for path, n in lines_of.items():
        folders[posixpath.dirname(path)] += n
    hubs = sorted(graph, key=lambda p: -len(back[p]) * len(graph[p]))[:TOP]
    used = sorted(graph, key=lambda p: -len(back[p]))[:TOP]
    near = sorted((p for p in graph if lines_of[p] >= NEAR_LIMIT), key=lambda p: -lines_of[p])
    out = [
        "# Code map",
        "",
        "Generated by `python scripts/code_map.py`; do not edit. aidm/ and scripts/ only.",
        "",
    ]
    out += [f"{len(graph)} files, {sum(lines_of.values()):,} lines.", ""]
    out += ["## Lines per folder", ""]
    out += table(
        "| folder | files | lines |",
        [[f, str(counts[f]), f"{n:,}"] for f, n in folders.most_common()],
    )

    def row(p: str) -> list[str]:
        return [
            p,
            str(lines_of[p]),
            str(len(back[p])),
            str(len(graph[p])),
            str(dependents(back, p)),
        ]

    head = "| file | lines | imported by | imports | depend on it |"
    out += ["", "## Hubs (imported by x imports): the files where a change reaches furthest", ""]
    out += table(head, [row(p) for p in hubs])
    out += ["", "## Most imported", ""] + table(head, [row(p) for p in used])
    out += ["", f"## Near the {LINE_LIMIT}-line limit (>= {NEAR_LIMIT})", ""]
    out += table("| file | lines |", [[p, str(lines_of[p])] for p in near])
    out += ["", f"## Families (>= {FAMILY_MIN} files with one name prefix in one folder)", ""]
    fams = [[k, str(len(m)), f"{sum(lines_of[p] for p in m):,}"] for k, m in families(list(graph))]
    return out + table("| family | files | lines |", fams) + [""]


def index_lines(graph: Graph, info: dict[str, tuple[int, str]]) -> list[str]:
    back = importers(graph)
    out = ["# Code index", "", "path | lines | imported by | imports | what it is", ""]
    for path in sorted(graph):
        lines, what = info[path]
        out.append(f"{path} | {lines} | {len(back[path])} | {len(graph[path])} | {what}")
    return out + [""]


def main(argv: list[str]) -> int:
    if "--no-scan" not in argv:
        scan()
    if not BLUEPRINT.exists():
        raise SystemExit(f"code map: no scan at {BLUEPRINT}; run without --no-scan")
    graph = build_graph(load_imports(BLUEPRINT))
    info = read_files(sorted(graph))
    (OUT / "CODEMAP.md").write_text("\n".join(codemap_lines(graph, info)), encoding="utf-8")
    (OUT / "INDEX.md").write_text("\n".join(index_lines(graph, info)), encoding="utf-8")
    print(f"code map: {len(graph)} files -> {OUT / 'CODEMAP.md'} and INDEX.md")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
