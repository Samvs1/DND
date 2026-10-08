"""OpenAI provider with a faked SDK client (no network): parsing, model choice, key never leaks."""

import base64
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aidm.server.assetgen import cli, openai_provider
from aidm.server.assetgen.openai_provider import OpenAIImageProvider
from aidm.server.assetgen.provider import ImageRequest, ProviderError, redact
from aidm.server.assetgen.synthetic_png import synthetic_png
from tests.unit.assetgen.helpers import SENTINEL, make_repo, read_text_tree

PNG = synthetic_png(8, 8, "openai fake", sheet=False)


class FakeImages:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls: list[dict[str, Any]] = []

    def _answer(self, kwargs: dict[str, Any]) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError(f"Incorrect API key provided: {SENTINEL}")
        usage = SimpleNamespace(
            input_tokens=1800,
            input_tokens_details=SimpleNamespace(text_tokens=300, image_tokens=1500),
            output_tokens=1056,
        )
        data = [SimpleNamespace(b64_json=base64.b64encode(PNG).decode("ascii"))]
        return SimpleNamespace(data=data, usage=usage)

    def generate(self, **kwargs: Any) -> SimpleNamespace:
        return self._answer(kwargs)

    def edit(self, **kwargs: Any) -> SimpleNamespace:
        kwargs["image_bytes"] = [f.read() for f in kwargs["image"]]
        return self._answer(kwargs)


class FakeClient:
    def __init__(self, failures: int = 0, ids: tuple[str, ...] = ()) -> None:
        listed = ids or ("dall-e-3", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini")
        self.models = SimpleNamespace(
            list=lambda: [SimpleNamespace(id=i, created=n) for n, i in enumerate(listed)]
        )
        self.images = FakeImages(failures)


def _request(refs: tuple[Path, ...] = ()) -> ImageRequest:
    return ImageRequest("a prompt", "1024x1024", "medium", True, refs)


def test_generate_parses_image_and_usage() -> None:
    client = FakeClient()
    provider = OpenAIImageProvider(SENTINEL, client)
    result = provider.generate(_request(), "gpt-image-1.5")
    assert result.image == PNG and result.usage.reported
    assert (result.usage.text_input_tokens, result.usage.image_input_tokens) == (300, 1500)
    sent = client.images.calls[0]
    assert sent["model"] == "gpt-image-1.5" and sent["background"] == "transparent"
    assert sent["quality"] == "medium" and sent["n"] == 1


def test_edit_sends_every_reference_image(tmp_path: Path) -> None:
    refs = []
    for n in range(3):
        path = tmp_path / f"ref{n}.png"
        path.write_bytes(synthetic_png(4, 4, str(n), sheet=False))
        refs.append(path)
    client = FakeClient()
    OpenAIImageProvider(SENTINEL, client).edit(_request(tuple(refs)), "gpt-image-1.5")
    assert client.images.calls[0]["image_bytes"] == [p.read_bytes() for p in refs]


def test_list_models_feeds_the_selection() -> None:
    from aidm.server.assetgen.costs import load_price_table
    from aidm.server.assetgen.provider import select_model

    models = OpenAIImageProvider(SENTINEL, FakeClient()).list_models()
    assert select_model(models, load_price_table().retired_models) == "gpt-image-1.5"


def test_key_never_appears_in_exception_text_or_repr() -> None:
    provider = OpenAIImageProvider(SENTINEL, FakeClient(failures=1))
    with pytest.raises(ProviderError) as err:
        provider.generate(_request(), "gpt-image-1.5")
    rendered = "".join(traceback.format_exception(err.value))
    assert SENTINEL not in str(err.value) and SENTINEL not in rendered
    assert "[redacted]" in str(err.value) and SENTINEL not in repr(provider)
    assert "sk-abc123456789" not in redact("bad key sk-abc123456789xyz")


def test_missing_key_is_refused_without_a_client() -> None:
    with pytest.raises(ProviderError, match="IMAGE_API_KEY is not set"):
        OpenAIImageProvider("")


def test_key_never_reaches_stdout_ledger_or_staged_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_repo(tmp_path)
    client = FakeClient(failures=1)
    monkeypatch.setattr(openai_provider, "make_openai_client", lambda _key: client)
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    monkeypatch.setenv("IMAGE_API_KEY", SENTINEL)
    lines: list[str] = []
    argv = ["--yes", "--only", "portrait.race.elf.f", "--v1-root", str(tmp_path / "v1")]
    code = cli.main(argv, root=tmp_path, out=lines.append)
    assert code == 0, lines
    assert any("attempt 1 failed" in line and "[redacted]" in line for line in lines)
    paths = cli.RepoPaths(tmp_path)
    written = read_text_tree(paths.ledger.parent) + read_text_tree(paths.staging)
    assert written and "gpt-image-1.5" in written
    assert SENTINEL not in "\n".join(lines) and SENTINEL not in written
