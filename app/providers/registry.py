"""One place that decides which model provider, if any, is available.

Call sites ask for a capability and get either a provider or `None`. `None` means
"run the deterministic path", which is what every caller already does when the
model is disabled or unreachable — the branch exists, it just used to be spelled
out with vendor-specific conditions in three different modules.

## Why there is no `deterministic` provider class

ADR-0001 proposed promoting the fallback paths to a provider. Reading them showed
that would be a fiction:

- the text fallback builds a `WorkInstruction` from the request object, not a
  JSON string from a prompt. Wrapping it in `TextProvider` would mean serialising
  a validated model to JSON purely so the caller could parse it back, adding a
  failure mode and removing none;
- local embeddings for indexed chunks are **precomputed at indexing time** and
  stored on the chunk. Nothing is invoked per query, so there is no call to put
  behind an interface.

A null object that no caller can use uniformly is not an abstraction, it is a
class. Returning `None` says the same thing and is honest about it. The
closed-perimeter profile in stage 1.4 gets what it needs from this too: with no
model configured, nothing here can reach the network.
"""

from __future__ import annotations

from app.core.settings import Settings, get_settings
from app.providers.base import EmbeddingProvider, TextProvider, VisionProvider
from app.providers.errors import ProviderNotConfiguredError

EMBEDDING_DIMENSIONS = 1536


def _model_is_configured(settings: Settings) -> bool:
    return bool(settings.openai_enabled and settings.openai_api_key)


def text_provider(settings: Settings | None = None) -> TextProvider | None:
    resolved = settings or get_settings()
    if not _model_is_configured(resolved):
        return None
    from app.providers.openai_api import OpenAICompatibleTextProvider

    try:
        return OpenAICompatibleTextProvider(
            api_key=resolved.openai_api_key,
            model=resolved.openai_model,
            timeout=resolved.openai_timeout_seconds,
        )
    except ProviderNotConfiguredError:
        return None


def vision_provider(settings: Settings | None = None) -> VisionProvider | None:
    resolved = settings or get_settings()
    if not _model_is_configured(resolved):
        return None
    from app.providers.openai_api import OpenAICompatibleVisionProvider

    try:
        return OpenAICompatibleVisionProvider(
            api_key=resolved.openai_api_key,
            model=resolved.openai_vision_model,
            timeout=resolved.openai_timeout_seconds,
        )
    except ProviderNotConfiguredError:
        return None


def embedding_provider(settings: Settings | None = None) -> EmbeddingProvider | None:
    resolved = settings or get_settings()
    if not _model_is_configured(resolved):
        return None
    from app.providers.openai_api import OpenAICompatibleEmbeddingProvider

    try:
        return OpenAICompatibleEmbeddingProvider(
            api_key=resolved.openai_api_key,
            model=resolved.openai_embedding_model,
            timeout=resolved.openai_timeout_seconds,
            dimensions=EMBEDDING_DIMENSIONS,
        )
    except ProviderNotConfiguredError:
        return None
