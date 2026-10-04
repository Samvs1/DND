"""Secrets gate: fail if any tracked or staged file contains a value from .env.

Only file paths are ever printed. Values and key names are never shown.
"""

from __future__ import annotations

import io
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

MIN_VALUE_LEN = 8


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_env_values(text: str) -> list[str]:
    """Return values (length >= 8) from KEY=VALUE lines; comments and blanks ignored."""
    values: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if len(value) >= MIN_VALUE_LEN:
            values.append(value)
    return values


def git_files(root: Path) -> list[str]:
    """Tracked files plus staged files (relative posix paths)."""
    names: set[str] = set()
    for args in (["ls-files"], ["diff", "--cached", "--name-only", "--diff-filter=ACMR"]):
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        names.update(n for n in result.stdout.splitlines() if n.strip())
    return sorted(names)


def scan_files(root: Path, env_values: Iterable[str], files: Iterable[str]) -> list[str]:
    """Return the relative paths of files that contain any of ``env_values``."""
    values = [v.encode("utf-8") for v in env_values if len(v) >= MIN_VALUE_LEN]
    hits: list[str] = []
    if not values:
        return hits
    for rel in files:
        path = root / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if any(v in data for v in values):
            hits.append(rel)
    return hits


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]).resolve() if args else repo_root()
    env_path = root / ".env"
    if not env_path.is_file():
        print("no .env, skipped")
        return 0
    values = parse_env_values(env_path.read_text(encoding="utf-8"))
    hits = scan_files(root, values, git_files(root))
    for rel in hits:
        print(rel)
    if hits:
        print(f"secrets: {len(hits)} file(s) contain secret values")
        return 1
    print("secrets: ok")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
