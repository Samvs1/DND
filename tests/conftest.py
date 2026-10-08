import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live tests need RUN_LIVE=1")
    live_dir = Path(__file__).parent.joinpath("live").resolve()
    for item in items:
        path = Path(str(item.fspath)).resolve()
        if path.name == "test_image_live.py":
            continue  # gated by RUN_LIVE_IMAGES=1 in the file itself (it spends money)
        if live_dir in path.parents:
            item.add_marker(skip_live)
