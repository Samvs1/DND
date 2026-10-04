"""Structure gate: AST-based limits on file size, function size and module shape."""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

MAX_FILE_LINES = 400
MAX_FUNC_LINES = 60
SCAN_DIRS = ("aidm", "scripts", "tests")
SKIP_PARTS = {".venv", "__pycache__", ".git", "node_modules"}
INIT_ASSIGNS = {"__version__", "__all__"}

Violation = tuple[str, int, str]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def iter_py_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for name in SCAN_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_PARTS.isdisjoint(path.relative_to(root).parts):
                found.append(path)
    return found


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _assign_names(node: ast.stmt) -> set[str]:
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def check_file_length(rel: str, source: str) -> list[Violation]:
    count = len(source.splitlines())
    if count > MAX_FILE_LINES:
        return [(rel, count, f"file-too-long ({count} > {MAX_FILE_LINES} lines)")]
    return []


def check_function_lengths(rel: str, tree: ast.Module) -> list[Violation]:
    out: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            size = (node.end_lineno or node.lineno) - node.lineno + 1
            if size > MAX_FUNC_LINES:
                msg = f"function-too-long {node.name} ({size} > {MAX_FUNC_LINES} lines)"
                out.append((rel, node.lineno, msg))
    return out


def check_star_imports(rel: str, tree: ast.Module) -> list[Violation]:
    out: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            out.append((rel, node.lineno, "star-import"))
    return out


def _is_future(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def check_reexport_shim(rel: str, path: Path, tree: ast.Module) -> list[Violation]:
    if path.name == "__init__.py":
        return []
    body = [
        n
        for n in tree.body
        if not _is_docstring(n) and not _is_future(n) and "__all__" not in _assign_names(n)
    ]
    if body and all(isinstance(n, ast.Import | ast.ImportFrom) for n in body):
        return [(rel, body[0].lineno, "reexport-shim (module only imports)")]
    return []


def check_init_content(rel: str, path: Path, tree: ast.Module) -> list[Violation]:
    if path.name != "__init__.py":
        return []
    out: list[Violation] = []
    for node in tree.body:
        if _is_docstring(node) or isinstance(node, ast.Import | ast.ImportFrom):
            continue
        names = _assign_names(node)
        if names and names <= INIT_ASSIGNS:
            continue
        out.append(
            (rel, node.lineno, "init-has-code (only docstring, __version__, __all__, imports)")
        )
    return out


def check_root_files(root: Path) -> list[Violation]:
    return [(p.name, 1, "py-at-repo-root") for p in sorted(root.glob("*.py"))]


def public_names(tree: ast.Module) -> dict[str, int]:
    names: dict[str, int] = {}
    for node in tree.body:
        is_def = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        if is_def and not node.name.startswith("_"):
            names[node.name] = node.lineno
    return names


def check_duplicate_public(root: Path, trees: dict[Path, ast.Module]) -> list[Violation]:
    seen: dict[str, dict[str, tuple[str, int]]] = {"rules": {}, "dm": {}}
    for path, tree in trees.items():
        rel_parts = path.relative_to(root).parts
        if len(rel_parts) < 3 or rel_parts[0] != "aidm" or rel_parts[1] not in seen:
            continue
        for name, line in public_names(tree).items():
            seen[rel_parts[1]].setdefault(name, (_rel(root, path), line))
    out: list[Violation] = []
    for name in sorted(seen["dm"]):
        if name in seen["rules"]:
            rules_rel, _ = seen["rules"][name]
            dm_rel, dm_line = seen["dm"][name]
            out.append((dm_rel, dm_line, f"duplicate-public-name {name} (also in {rules_rel})"))
    return out


def parse_files(root: Path, files: list[Path]) -> tuple[dict[Path, ast.Module], list[Violation]]:
    trees: dict[Path, ast.Module] = {}
    errors: list[Violation] = []
    for path in files:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            line = getattr(exc, "lineno", None) or 1
            errors.append((_rel(root, path), line, "unparseable"))
    return trees, errors


def check_tree(root: Path) -> list[Violation]:
    """Run every rule against the repo rooted at ``root``."""
    files = iter_py_files(root)
    trees, violations = parse_files(root, files)
    violations.extend(check_root_files(root))
    for path, tree in trees.items():
        rel = _rel(root, path)
        source = path.read_text(encoding="utf-8")
        violations.extend(check_file_length(rel, source))
        violations.extend(check_function_lengths(rel, tree))
        violations.extend(check_star_imports(rel, tree))
        violations.extend(check_reexport_shim(rel, path, tree))
        violations.extend(check_init_content(rel, path, tree))
    violations.extend(check_duplicate_public(root, trees))
    return sorted(violations)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]).resolve() if args else repo_root()
    violations = check_tree(root)
    for rel, line, rule in violations:
        print(f"{rel}:{line} {rule}")
    if violations:
        print(f"structure: {len(violations)} violation(s)")
        return 1
    print("structure: ok")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
