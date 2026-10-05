"""Builds the one `LlmClient` for the process from `LlmSettings` (SPEC 4, 6.8, Appendix A).

Public API: `make_llm_client(settings, log=None) -> LlmClient`:
- `settings.fake` (`AIDM_FAKE_LLM=1`) -> FAKE mode over `FakeLLM` (deterministic default script);
- no `DEEPSEEK_API_KEY` -> DISABLED mode (`DisabledBackend`): every call returns an `LlmFailure`,
  callers use template fallbacks and the host sees the no-AI banner (`client.available` False);
- otherwise LIVE mode over `OpenAIBackend` (DeepSeek). Call `await client.discover_models()` once
  at startup.
"""

from aidm.dm.fake_llm import FakeLLM
from aidm.dm.llm_backend import DisabledBackend
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode
from aidm.dm.openai_backend import OpenAIBackend


def make_llm_client(settings: LlmSettings, log: LlmCallLog | None = None) -> LlmClient:
    if settings.fake:
        return LlmClient(FakeLLM(), settings, LlmMode.FAKE, log)
    if not settings.api_key:
        return LlmClient(DisabledBackend(), settings, LlmMode.DISABLED, log)
    backend = OpenAIBackend(settings.api_key, settings.base_url, settings.timeout_s)
    return LlmClient(backend, settings, LlmMode.LIVE, log)
