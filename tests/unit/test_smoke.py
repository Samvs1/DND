import aidm


def test_version_string() -> None:
    assert isinstance(aidm.__version__, str)
    assert aidm.__version__ == "0.1.0"
