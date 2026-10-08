"""Opt-in live smoke test for the image provider (RUN_LIVE_IMAGES=1): exactly ONE small image.

It lists the models from the API, lets `select_model` choose the current GPT Image id, books the
call in the real spend ledger (logs/asset_spend.json, so it counts toward the cap), makes ONE
low-quality 1024x1024 generate call and prints the model id and the real cost. The key is never
printed. The image is only checked for being a PNG and is kept in artifacts/assets/smoke/.
"""

import os
from collections.abc import Callable

import pytest

from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.ledger import BudgetGuard
from aidm.server.assetgen.openai_provider import OpenAIImageProvider
from aidm.server.assetgen.provider import ImageRequest, select_model
from tests.live.conftest import ROOT

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_IMAGES") != "1", reason="set RUN_LIVE_IMAGES=1 to run"
)

PROMPT = (
    "A single small painted icon of an unlit wooden torch on a plain dark background, "
    "painterly dark fantasy style, centred, no text, no watermark."
)


def test_live_image_smoke(live_env: dict[str, str], live_say: Callable[[str], None]) -> None:
    provider = OpenAIImageProvider(live_env.get("IMAGE_API_KEY", ""))
    table = load_price_table()
    model = select_model(provider.list_models(), table.retired_models)
    request = ImageRequest(prompt=PROMPT, size="1024x1024", quality="low", transparent=False)
    estimate = table.worst_case_eur(
        model=model, prompt=PROMPT, size=request.size, quality=request.quality, references=0
    )
    guard = BudgetGuard(ROOT / "logs" / "asset_spend.json", cap_eur=8.0)
    call_id = guard.reserve(
        keys=["smoke.torch"],
        model=model,
        endpoint=request.endpoint,
        size=request.size,
        quality=request.quality,
        attempt=1,
        estimate_eur=estimate,
    )
    try:
        result = provider.generate(request, model)
    except Exception:
        guard.fail(call_id)
        raise
    cost = table.actual_eur(model, result.usage)
    guard.settle(call_id, cost)
    out_dir = ROOT / "artifacts" / "assets" / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "smoke_torch.png").write_bytes(result.image)
    assert result.image[:8] == b"\x89PNG\r\n\x1a\n"
    live_say(
        f"LIVE image smoke: model={result.model} (listed pick {model}) bytes={len(result.image)} "
        f"usage_reported={result.usage.reported} out_tokens={result.usage.output_tokens} "
        f"cost_eur={cost} worst_case_eur={estimate}"
    )
