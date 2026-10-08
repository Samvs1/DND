"""Image provider interface and model selection (Addendum B.2).

A provider lists the models its key can use, generates an image from a prompt, and edits (makes a
new image from a prompt plus 1-3 reference images). Every call returns the image bytes and the
token usage the response reported, so the budget guard can book the actual cost.

`select_model` picks the CURRENT GPT Image model from a listed model set: retired ids (from
data/asset_costs.json) and their dated snapshots are never chosen; stable ids beat alpha/preview
ids, a higher version beats a lower one, a full model beats a mini one, the base id beats a dated
snapshot. No model id is hardcoded here.

Public API: `ImageRequest`, `ImageResult`, `ImageUsage`, `ModelInfo`, `ImageProvider`,
`ProviderError`, `ModelUnavailable`, `select_model`, `redact`, `SHEET_MARK` (the phrase every
sheet prompt carries).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_GPT_IMAGE = re.compile(r"^gpt-image-(\d+(?:\.\d+)*)(.*)$")
_DATED = re.compile(r"^-\d{4}-\d{2}-\d{2}$")
_UNSTABLE = ("alpha", "beta", "preview", "experimental")
_KEYLIKE = re.compile(r"sk-[A-Za-z0-9*_\-]{4,}")
MAX_ERROR_CHARS = 300
SHEET_MARK = "4x4 sprite sheet"
VERIFY_HINT = (
    "No current GPT Image model is available to this API key. Open "
    "platform.openai.com > Settings > Organization > General, complete organisation "
    "verification, wait for access, then run again."
)


@dataclass(frozen=True)
class ImageUsage:
    text_input_tokens: int = 0
    image_input_tokens: int = 0
    output_tokens: int = 0
    reported: bool = False


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    size: str
    quality: str
    transparent: bool
    references: tuple[Path, ...] = ()

    @property
    def endpoint(self) -> str:
        return "edit" if self.references else "generate"


@dataclass(frozen=True)
class ImageResult:
    image: bytes
    model: str
    usage: ImageUsage


@dataclass(frozen=True)
class ModelInfo:
    id: str
    created: int = 0


class ProviderError(Exception):
    """A provider call failed. The message never carries key material."""


class ModelUnavailable(ProviderError):
    """No usable GPT Image model is listed for this key."""


class ImageProvider(Protocol):
    name: str

    def list_models(self) -> list[ModelInfo]: ...

    def generate(self, request: ImageRequest, model: str) -> ImageResult: ...

    def edit(self, request: ImageRequest, model: str) -> ImageResult: ...


def redact(text: str, secret: str = "") -> str:
    """`text` with the secret and anything key-shaped removed, cut to a sane length."""
    out = text.replace(secret, "[redacted]") if secret else text
    return _KEYLIKE.sub("[redacted]", out)[:MAX_ERROR_CHARS]


def _is_retired(model_id: str, retired: Iterable[str]) -> bool:
    for old in retired:
        if model_id == old:
            return True
        if model_id.startswith(old) and _DATED.match(model_id[len(old) :]):
            return True
    return False


def _rank(info: ModelInfo) -> tuple[bool, tuple[int, ...], bool, bool, int]:
    match = _GPT_IMAGE.match(info.id)
    assert match is not None
    version = tuple(int(p) for p in match.group(1).split("."))
    suffix = match.group(2)
    stable = not any(word in suffix for word in _UNSTABLE)
    return (stable, version, "mini" not in suffix, suffix == "", info.created)


def select_model(models: Iterable[ModelInfo], retired: Iterable[str]) -> str:
    """The current GPT Image model id among `models`; `ModelUnavailable` when there is none."""
    old = tuple(retired)
    usable = [m for m in models if _GPT_IMAGE.match(m.id) and not _is_retired(m.id, old)]
    if not usable:
        raise ModelUnavailable(VERIFY_HINT)
    return max(usable, key=_rank).id
