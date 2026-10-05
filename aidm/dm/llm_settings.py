"""LLM settings from the environment and startup model discovery (SPEC 4 DeepSeek, Appendix A).

Public API:
- `DEFAULT_MODEL_FAST` / `DEFAULT_MODEL_QUALITY`: the verified current DeepSeek ids
  (docs/DECISIONS.md M4.1). `DEEPSEEK_MODEL_FAST` / `DEEPSEEK_MODEL_QUALITY` override them.
- `LlmSettings`: key presence (the key itself is held privately and never logged or repr'd),
  model ids, fake flag, timeouts, retry bound, token floors and the log path.
- `llm_settings_from_env(environ) -> LlmSettings`: reads the Appendix A variables.
- `resolve_models(available, fast, quality) -> ModelChoice`: keeps a configured id that the
  provider lists; otherwise picks the closest listed id for the role ("flash" for FAST, "pro"
  for QUALITY, else the first listed) and records a warning. An empty list (discovery failed)
  keeps the configured ids.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from aidm.dm.llm_types import LlmRole

DEFAULT_MODEL_FAST = "deepseek-flash"
DEFAULT_MODEL_QUALITY = "deepseek-v4-pro"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
STRUCTURED_MAX_TOKENS = 4000
DEFAULT_LOG_PATH = Path("logs") / "llm.jsonl"
_ROLE_HINT = {LlmRole.FAST: "flash", LlmRole.QUALITY: "pro"}


@dataclass(frozen=True)
class LlmSettings:
    api_key: str | None = field(default=None, repr=False)
    base_url: str = DEEPSEEK_BASE_URL
    model_fast: str = DEFAULT_MODEL_FAST
    model_quality: str = DEFAULT_MODEL_QUALITY
    fake: bool = False
    timeout_s: float = 45.0
    stream_idle_timeout_s: float = 20.0
    max_retries: int = 2
    structured_max_tokens: int = STRUCTURED_MAX_TOKENS
    max_tokens_cap: int = 16000
    log_path: Path | None = DEFAULT_LOG_PATH

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def model_for(self, role: LlmRole) -> str:
        return self.model_fast if role is LlmRole.FAST else self.model_quality


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value else default
    except ValueError:
        return default


def llm_settings_from_env(environ: Mapping[str, str]) -> LlmSettings:
    return LlmSettings(
        api_key=(environ.get("DEEPSEEK_API_KEY") or "").strip() or None,
        model_fast=environ.get("DEEPSEEK_MODEL_FAST") or DEFAULT_MODEL_FAST,
        model_quality=environ.get("DEEPSEEK_MODEL_QUALITY") or DEFAULT_MODEL_QUALITY,
        fake=_flag(environ.get("AIDM_FAKE_LLM")),
        timeout_s=_float(environ.get("AIDM_LLM_TIMEOUT_S"), 45.0),
    )


@dataclass(frozen=True)
class ModelChoice:
    fast: str
    quality: str
    warnings: tuple[str, ...] = ()


def _pick(role: LlmRole, wanted: str, available: Sequence[str]) -> tuple[str, str | None]:
    if wanted in available:
        return wanted, None
    hinted = [m for m in available if _ROLE_HINT[role] in m]
    chosen = hinted[0] if hinted else available[0]
    return chosen, f"model {wanted!r} ({role.value}) not listed by the provider; using {chosen!r}"


def resolve_models(available: Sequence[str], fast: str, quality: str) -> ModelChoice:
    if not available:
        return ModelChoice(fast, quality)
    fast_id, w1 = _pick(LlmRole.FAST, fast, available)
    quality_id, w2 = _pick(LlmRole.QUALITY, quality, available)
    return ModelChoice(fast_id, quality_id, tuple(w for w in (w1, w2) if w))
