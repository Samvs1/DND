"""GET /manual (HTML shell) and GET /api/manual (the Markdown text) (M14.1)."""

from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from aidm.data.manual_gen import MANUAL_PATH
from aidm.server.manual_routes import add_manual_routes
from tests.session.server_fixtures import make_app


def test_manual_page_and_text(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        page = client.get("/manual")
        assert page.status_code == 200 and "text/html" in page.headers["content-type"]
        assert "manual_page.js" in page.text
        text = client.get("/api/manual")
        assert text.status_code == 200 and "text/markdown" in text.headers["content-type"]
        assert text.text == MANUAL_PATH.read_text(encoding="utf-8")
        assert "| 1 | 25 gp |" in text.text


def test_missing_manual_is_a_plain_404(tmp_path: Path) -> None:
    app = FastAPI()
    add_manual_routes(app, tmp_path, tmp_path / "nope.md")
    client = TestClient(app)
    assert client.get("/api/manual").status_code == 404
    assert client.get("/manual").status_code == 200  # the placeholder shell
