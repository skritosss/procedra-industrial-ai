"""Model-provider layer.

Everything that talks to a language, vision or embedding model belongs here.
After stage 1.2 of ADR-0001 no vendor SDK may be imported outside this package,
and a test enforces that rather than a convention.
"""

from app.providers.base import EmbeddingProvider, TextProvider, VisionProvider
from app.providers.errors import (
    ProviderEgressBlockedError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnavailableError,
)

__all__ = [
    "EmbeddingProvider",
    "ProviderEgressBlockedError",
    "ProviderError",
    "ProviderNotConfiguredError",
    "ProviderResponseError",
    "ProviderUnavailableError",
    "TextProvider",
    "VisionProvider",
]
