"""Static checks of the frontend (no browser): handler coverage, strings.js discipline (M7.1)."""

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent.parent / "aidm" / "web"
JS = WEB / "js"


def _js_files() -> list[Path]:
    return sorted(JS.rglob("*.js"))


def _strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(re.sub(r"^\s*//.*$", "", line) for line in source.splitlines())


def server_types() -> list[str]:
    protocol = json.loads((WEB / "protocol.json").read_text(encoding="utf-8"))
    return list(protocol["server"]["types"])


def handler_keys() -> set[str]:
    source = (JS / "handlers.js").read_text(encoding="utf-8")
    block = source.split("export const HANDLERS = {", 1)[1].split("\n};", 1)[0]
    return set(re.findall(r"^\s+([a-z_]+):", block, flags=re.M))


def string_keys() -> set[str]:
    """`group.key` pairs of strings.js (groups at 2 spaces, keys at 4 spaces)."""
    keys: set[str] = set()
    group = ""
    for line in (JS / "strings.js").read_text(encoding="utf-8").splitlines():
        top = re.match(r"^  (\w+): \{", line)
        if top:
            group = top.group(1)
            continue
        leaf = re.match(r"^    (\w+): ", line)
        if leaf and group:
            keys.add(f"{group}.{leaf.group(1)}")
    return keys


def test_every_server_message_has_a_handler() -> None:
    types = server_types()
    assert len(types) >= 20
    assert set(types) - handler_keys() == set()


def test_handlers_do_not_list_unknown_types() -> None:
    assert handler_keys() - set(server_types()) == set()


def test_unknown_message_is_ignored_not_shown() -> None:
    source = (JS / "handlers.js").read_text(encoding="utf-8")
    assert "console.debug" in source


def test_strings_js_exists_with_lobby_keys() -> None:
    keys = string_keys()
    for key in ("app.title", "lobby.start", "join.button", "banner.fallback", "errors.generic"):
        assert key in keys


def test_every_t_key_exists_in_strings() -> None:
    known = string_keys()
    used: set[str] = set()
    for path in _js_files():
        if path.name == "strings.js":
            continue
        used |= set(re.findall(r"\bt\('([a-z]+\.[A-Za-z]+)'\)", path.read_text(encoding="utf-8")))
    assert used, "the lobby must use strings.js keys"
    assert used - known == set()


def test_no_user_visible_literals_outside_strings_js() -> None:
    """Heuristic: no capitalised multi-word literal and no literal textContent assignment."""
    phrase = re.compile(r"""(['"`])([A-Z][a-z]+(?: [A-Za-z']+)+[.!?]?)\1""")
    assigned = re.compile(r"""\.(?:textContent|innerText|innerHTML)\s*=\s*['"`][^'"`]*[A-Za-z]""")
    offenders: list[str] = []
    for path in _js_files():
        if path.name == "strings.js":
            continue
        code = _strip_comments(path.read_text(encoding="utf-8"))
        for match in list(phrase.finditer(code)) + list(assigned.finditer(code)):
            offenders.append(f"{path.name}: {match.group(0)}")
    assert offenders == []
