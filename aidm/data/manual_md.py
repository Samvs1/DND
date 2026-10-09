"""Markdown helpers for the generated player-manual sections (M14.1). Pure string functions."""

from collections.abc import Iterable, Sequence


def cell(text: object) -> str:
    """One table cell: a single line, pipes escaped."""
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "/").strip()


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(cell(h) for h in headers) + " |"]
    lines.append("|" + "|".join(" --- " for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(cell(c) for c in row) + " |")
    return "\n".join(lines)


def words(slug: str) -> str:
    """'light-hammers' -> 'light hammers'."""
    return slug.replace("-", " ").replace("_", " ")


def join(items: Iterable[str], empty: str = "none") -> str:
    values = [words(i) for i in items]
    return ", ".join(values) if values else empty


def signed(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)
