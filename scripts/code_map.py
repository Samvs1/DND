"""The code map (owner 2026-10-27): what each file is for, who imports it, and the hub files.

  python scripts/code_map.py     about a second; no third-party tools

Reads every .py and .js file under aidm/ and scripts/ (tests are not coupling): Python imports
with `ast` (also the ones inside functions), JS imports with one pattern (every import in
aidm/web/js is a relative path). Writes, under artifacts/codemap/ (gitignored):
- CODEMAP.md: lines per folder, the hubs (imported by many AND importing many: fan-in x fan-out),
  the most imported files, the files near the 400-line limit, and file families (one name
  prefix, many files in one folder);
- INDEX.md: one line per file: path, lines, imported by, imports, the first line of its docstring
  or header comment. Grep it to find where a concept lives before opening files.
"""

import ast
import io
import posixpath
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "codemap"
CODE_DIRS = ("aidm", "scripts")
LINE_LIMIT, NEAR_LIMIT, FAMILY_MIN, TOP = 400, 340, 6, 20
JS_IMPORT = re.compile(r"""(?:\bfrom|\bimport)\s*\(?\s*['"](\.{1,2}/[^'"]+)['"]""")

Graph = dict[str, set[str]]
Imports = list[tuple[str, ...]]  # each import: the strings it may name, the most specific first


def code_files(root: Path) -> list[str]:
    found = (p for d in CODE_DIRS for p in (root / d).rglob("*") if p.suffix in (".py", ".js"))
    return sorted(p.relative_to(root).as_posix() for p in found if "__pycache__" not in p.parts)


def py_imports(tree: ast.Module) -> Imports:
    """`import a.b` names a.b; `from a.b import c` names a.b.c if that is a module, else a.b."""
    out: Imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(alias.name,) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out += [(f"{node.module}.{alias.name}", node.module) for alias in node.names]
    return out


def resolve(src: str, imp: str, known: set[str]) -> str | None:
    """The file an import string names, or None (stdlib, third party, unknown)."""
    if imp.startswith("."):
        path = posixpath.normpath(posixpath.join(posixpath.dirname(src), imp))
        candidates = [path, f"{path}.js"]
    else:
        base = imp.replace(".", "/")
        candidates = [f"{base}.py", f"{base}/__init__.py"]
    return next((c for c in candidates if c in known and c != src), None)


def build_graph(imports: dict[str, Imports]) -> Graph:
    known = set(imports)
    graph: Graph = {src: set() for src in imports}
    for src, imps in imports.items():
        for options in imps:
            hit = next((d for imp in options if (d := resolve(src, imp, known))), None)
            if hit:
                graph[src].add(hit)
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


def summary_line(text: str, tree: ast.Module | None) -> str:
    if tree is not None:
        doc = (ast.get_docstring(tree) or "").strip()
        return doc.splitlines()[0] if doc else ""
    head = text.lstrip().splitlines()[:1]
    if head and head[0].startswith(("//", "/*")):
        return head[0].lstrip("/* ").strip()
    return ""


def parse(rel: str, text: str) -> tuple[int, str, Imports]:
    """Lines, the one-line purpose and the imports of one file."""
    if rel.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return len(text.splitlines()), "", []
        return len(text.splitlines()), summary_line(text, tree), py_imports(tree)
    return len(text.splitlines()), summary_line(text, None), [(m,) for m in JS_IMPORT.findall(text)]


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


def main(root: Path = ROOT) -> int:
    parsed = {
        rel: parse(rel, (root / rel).read_text(encoding="utf-8", errors="replace"))
        for rel in code_files(root)
    }
    graph = build_graph({rel: imps for rel, (_, _, imps) in parsed.items()})
    info = {rel: (lines, what) for rel, (lines, what, _) in parsed.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CODEMAP.md").write_text("\n".join(codemap_lines(graph, info)), encoding="utf-8")
    (OUT / "INDEX.md").write_text("\n".join(index_lines(graph, info)), encoding="utf-8")
    print(f"code map: {len(graph)} files -> {OUT / 'CODEMAP.md'} and INDEX.md")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
