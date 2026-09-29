from functools import lru_cache

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.groq import GroqProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Single place that knows which concrete provider to build.

    Adding a new backend (OpenAI, Azure OpenAI, ...) means adding a branch
    here and an implementation module under `app/llm/` - the agent runtime
    never needs to change.
    """
    return GroqProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        base_url=settings.groq_base_url,
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())
