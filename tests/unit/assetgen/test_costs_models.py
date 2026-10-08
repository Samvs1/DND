"""Price table, worst-case and actual cost, and GPT Image model selection (Addendum B.2, B.4)."""

import pytest

from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.provider import ImageUsage, ModelInfo, ModelUnavailable, select_model

TABLE = load_price_table()
RETIRED = TABLE.retired_models


def _ids(*names: str) -> list[ModelInfo]:
    return [ModelInfo(n, i) for i, n in enumerate(names)]


def test_select_model_picks_newest_gpt_image_and_avoids_retired() -> None:
    models = _ids("dall-e-3", "gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5", "gpt-4o")
    assert select_model(models, RETIRED) == "gpt-image-1.5"


def test_select_model_prefers_a_higher_version_full_base_stable_id() -> None:
    models = _ids("gpt-image-1.5", "gpt-image-2-mini", "gpt-image-2", "gpt-image-2-2026-09-01")
    assert select_model(models, RETIRED) == "gpt-image-2"
    assert select_model(_ids("gpt-image-1.5", "gpt-image-3-preview"), RETIRED) == "gpt-image-1.5"
    assert select_model(_ids("gpt-image-0721-mini-alpha", "gpt-image-1.5"), RETIRED) == (
        "gpt-image-1.5"
    )


def test_select_model_never_returns_a_retired_id_or_its_dated_snapshot() -> None:
    with pytest.raises(ModelUnavailable) as err:
        select_model(_ids("gpt-image-1", "gpt-image-1-2025-04-23", "dall-e-3"), RETIRED)
    assert "organisation verification" in str(err.value).lower()
    assert "gpt-image-1" in RETIRED
    assert select_model(_ids("gpt-image-1", "gpt-image-1-mini"), RETIRED) == "gpt-image-1-mini"


def test_golden_worst_case_estimate() -> None:
    # 299 chars -> 299 // 3 + 1 = 100 text tokens; 3 refs x 1000 image tokens; medium 1024x1024
    # = 1056 output tokens; most expensive row 5/10/40 USD per 1M tokens:
    # (100*5 + 3000*10 + 1056*40) / 1e6 = 0.07274 USD; x 1.25 margin x 0.95 EUR = 0.08637875
    cost = TABLE.worst_case_eur(
        model=None, prompt="x" * 299, size="1024x1024", quality="medium", references=3
    )
    assert cost == pytest.approx(0.0864)


def test_unknown_model_is_priced_at_the_most_expensive_row() -> None:
    args = {"prompt": "p" * 90, "size": "1024x1024", "quality": "medium", "references": 1}
    unknown = TABLE.worst_case_eur(model="gpt-image-9", **args)
    mini = TABLE.worst_case_eur(model="gpt-image-1-mini", **args)
    assert unknown == TABLE.worst_case_eur(model=None, **args) > mini


def test_golden_actual_cost_from_usage() -> None:
    # gpt-image-1.5 row 5/10/40: (300*5 + 1500*10 + 1056*40) / 1e6 = 0.05874 USD
    # x 0.95 = 0.055803 EUR, rounded up to 1/10000 -> 0.0559
    usage = ImageUsage(300, 1500, 1056, reported=True)
    assert TABLE.actual_eur("gpt-image-1.5", usage) == pytest.approx(0.0559)
    assert TABLE.actual_eur("gpt-image-1.5", ImageUsage()) is None


def test_actual_cost_never_exceeds_worst_case_for_the_same_call() -> None:
    worst = TABLE.worst_case_eur(
        model="gpt-image-1.5", prompt="y" * 900, size="1024x1024", quality="medium", references=3
    )
    actual = TABLE.actual_eur("gpt-image-1.5", ImageUsage(300, 3000, 1056, reported=True))
    assert actual is not None and actual <= worst


def test_price_table_is_conservative_and_complete() -> None:
    assert TABLE.usd_to_eur >= 0.9 and TABLE.safety_margin >= 1.0
    assert TABLE.default_quality == "medium"
    for quality in ("low", "medium", "high"):
        assert TABLE.sheet_size in TABLE.output_tokens[quality]
        for size in TABLE.request_sizes.values():
            assert size in TABLE.output_tokens[quality]
