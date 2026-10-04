from pathlib import Path

import pytest

from .helpers import load_script, write

cs = load_script("check_structure")


def rules(root: Path) -> list[str]:
    return [v[2].split(" ")[0] for v in cs.check_tree(root)]


def test_clean_tree_passes(tmp_path: Path) -> None:
    write(tmp_path, "aidm/__init__.py", '"""pkg."""\n__version__ = "1"\n')
    write(tmp_path, "aidm/mod.py", "def f() -> int:\n    return 1\n")
    assert cs.check_tree(tmp_path) == []
    assert cs.main([str(tmp_path)]) == 0


def test_file_too_long_fails(tmp_path: Path) -> None:
    write(tmp_path, "aidm/big.py", "x = 1\n" * 401)
    assert rules(tmp_path) == ["file-too-long"]


def test_file_at_limit_passes(tmp_path: Path) -> None:
    write(tmp_path, "aidm/ok.py", "x = 1\n" * 400)
    assert rules(tmp_path) == []


def test_function_too_long_fails(tmp_path: Path) -> None:
    body = "def f() -> None:\n" + "    pass\n" * 60
    write(tmp_path, "aidm/fn.py", body)
    assert rules(tmp_path) == ["function-too-long"]


def test_function_at_limit_passes(tmp_path: Path) -> None:
    body = "def f() -> None:\n" + "    pass\n" * 59
    write(tmp_path, "aidm/fn.py", body)
    assert rules(tmp_path) == []


def test_method_too_long_fails(tmp_path: Path) -> None:
    body = "class A:\n    def m(self) -> None:\n" + "        pass\n" * 60
    write(tmp_path, "aidm/cls.py", body)
    assert rules(tmp_path) == ["function-too-long"]


def test_root_py_fails(tmp_path: Path) -> None:
    write(tmp_path, "setup.py", "x = 1\n")
    assert rules(tmp_path) == ["py-at-repo-root"]


def test_no_root_py_passes(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[project]\n")
    assert rules(tmp_path) == []


def test_star_import_fails(tmp_path: Path) -> None:
    write(tmp_path, "tests/test_x.py", "from os.path import *\nx = join\n")
    assert rules(tmp_path) == ["star-import"]


def test_explicit_import_passes(tmp_path: Path) -> None:
    write(tmp_path, "tests/test_x.py", "from os.path import join\nx = join\n")
    assert rules(tmp_path) == []


def test_reexport_shim_fails(tmp_path: Path) -> None:
    src = (
        '"""shim."""\nfrom __future__ import annotations\nfrom os import path\n__all__ = ["path"]\n'
    )
    write(tmp_path, "aidm/shim.py", src)
    assert rules(tmp_path) == ["reexport-shim"]


def test_module_with_logic_is_not_shim(tmp_path: Path) -> None:
    write(tmp_path, "aidm/real.py", "from os import path\n\nX = path.sep\n")
    assert rules(tmp_path) == []


def test_init_with_code_fails(tmp_path: Path) -> None:
    write(tmp_path, "aidm/__init__.py", '"""pkg."""\ndef helper() -> int:\n    return 1\n')
    assert rules(tmp_path) == ["init-has-code"]


def test_init_with_allowed_content_passes(tmp_path: Path) -> None:
    src = '"""pkg."""\nfrom os import path\n__version__ = "1"\n__all__ = ["path"]\n'
    write(tmp_path, "aidm/__init__.py", src)
    assert rules(tmp_path) == []


def test_duplicate_public_name_fails(tmp_path: Path) -> None:
    write(tmp_path, "aidm/rules/a.py", "def roll() -> int:\n    return 1\n")
    write(tmp_path, "aidm/dm/b.py", "def roll() -> int:\n    return 2\n")
    assert rules(tmp_path) == ["duplicate-public-name"]


def test_distinct_and_private_names_pass(tmp_path: Path) -> None:
    write(
        tmp_path,
        "aidm/rules/a.py",
        "def roll() -> int:\n    return 1\n\ndef _h() -> int:\n    return 0\n",
    )
    write(
        tmp_path,
        "aidm/dm/b.py",
        "def narrate() -> int:\n    return 2\n\ndef _h() -> int:\n    return 0\n",
    )
    assert rules(tmp_path) == []


def test_venv_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, "tests/.venv/bad.py", "from os import *\n")
    assert rules(tmp_path) == []


def test_main_prints_violation_line_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "aidm/big.py", "x = 1\n" * 401)
    assert cs.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("aidm/big.py:401 file-too-long")
    assert out.isascii()
