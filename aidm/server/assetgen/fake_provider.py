"""`FakeImageProvider`: deterministic, offline stand-in for the OpenAI provider (Addendum B.6).

It lists a scriptable model set, returns synthetic PNGs (transparent background; a 4x4 grid when
the prompt asks for a sheet) scaled down from the requested size by `scale`, reports fake token
usage, and can fail on chosen call numbers (1-based) to test retries. `on_call(request)` runs
inside every call before the image is returned, so a test can inspect the ledger mid-call.

Public API: `FakeImageProvider`, `DEFAULT_FAKE_MODELS`, `DEFAULT_FAKE_USAGE`.
"""

from collections.abc import Callable, Iterable

from aidm.server.assetgen.provider import (
    SHEET_MARK,
    ImageRequest,
    ImageResult,
    ImageUsage,
    ModelInfo,
    ProviderError,
)
from aidm.server.assetgen.synthetic_png import synthetic_png

DEFAULT_FAKE_MODELS = (
    ModelInfo("dall-e-3", 1_698_000_000),
    ModelInfo("gpt-image-1", 1_745_000_000),
    ModelInfo("gpt-image-1-mini", 1_760_000_000),
    ModelInfo("gpt-image-1.5", 1_765_000_000),
)
DEFAULT_FAKE_USAGE = ImageUsage(
    text_input_tokens=300, image_input_tokens=0, output_tokens=1056, reported=True
)


class FakeImageProvider:
    name = "fake"

    def __init__(
        self,
        *,
        models: Iterable[ModelInfo] = DEFAULT_FAKE_MODELS,
        fail_on: Iterable[int] = (),
        usage: ImageUsage = DEFAULT_FAKE_USAGE,
        image_tokens_per_reference: int = 500,
        on_call: Callable[[ImageRequest], None] | None = None,
        scale: int = 16,
    ) -> None:
        self.models = list(models)
        self.fail_on = frozenset(fail_on)
        self.usage = usage
        self.image_tokens_per_reference = image_tokens_per_reference
        self.on_call = on_call
        self.scale = max(1, scale)
        self.calls: list[tuple[str, ImageRequest, str]] = []

    def list_models(self) -> list[ModelInfo]:
        return list(self.models)

    def generate(self, request: ImageRequest, model: str) -> ImageResult:
        return self._call("generate", request, model)

    def edit(self, request: ImageRequest, model: str) -> ImageResult:
        if not request.references:
            raise ProviderError("edit needs at least one reference image")
        return self._call("edit", request, model)

    def _call(self, endpoint: str, request: ImageRequest, model: str) -> ImageResult:
        self.calls.append((endpoint, request, model))
        number = len(self.calls)
        if self.on_call is not None:
            self.on_call(request)
        if number in self.fail_on:
            raise ProviderError(f"fake failure on call {number}")
        width, height = (int(p) // self.scale for p in request.size.split("x"))
        image = synthetic_png(width, height, request.prompt, sheet=SHEET_MARK in request.prompt)
        usage = ImageUsage(
            text_input_tokens=self.usage.text_input_tokens,
            image_input_tokens=self.usage.image_input_tokens
            + self.image_tokens_per_reference * len(request.references),
            output_tokens=self.usage.output_tokens,
            reported=self.usage.reported,
        )
        return ImageResult(image=image, model=model, usage=usage)
