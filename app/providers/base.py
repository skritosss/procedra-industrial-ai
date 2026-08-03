"""Capability interfaces for the model layer.

Three places in the application talk to a hosted model, and each one builds an
OpenAI client itself. That welds the product to one vendor: a plant network with
no route to a hosted API silently degrades to the deterministic fallback, and the
first security-review question — where is our data processed — has an answer that
ends the conversation.

These protocols are deliberately the smallest thing that covers what those three
call sites already do. Nothing here is aspirational; every method exists because
a caller needs it today.

Stage 1.1 of ADR-0001: the interfaces only. No implementation, no registry, and
no call site touched, so this package is inert until stage 1.2 wires it in.

## Two deviations from ADR-0001, decided after reading the call sites

**Providers return raw JSON text, not domain objects.** The ADR proposed
`VisionProvider.describe(...) -> FrameAnalysis`. Returning a domain model would
put `app.schemas` inside the provider boundary and oblige every future provider —
including a local model behind a corporate gateway — to know the instruction
schema. Parsing and validation already live at the call sites, next to the
fallback that handles a bad payload. They stay there.

**Timeout is provider configuration, not a per-call argument.** All three call
sites set it once when constructing the client and never vary it per request. A
per-call parameter would be an interface that nothing uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class TextProvider(Protocol):
    """Produce a JSON document from a prompt.

    The application asks for structured output and validates it against a Pydantic
    model afterwards, so the contract here is "a string that should parse as
    JSON" rather than free text. A provider that cannot honour a JSON-object
    response format is still valid — it just fails validation downstream and the
    caller falls back, which is the behaviour today.
    """

    @property
    def name(self) -> str:
        """Stable identifier recorded in the audit trail beside each draft."""

    def complete_json(self, *, system: str, prompt: str) -> str:
        """Return the model's answer as raw JSON text.

        Raises `ProviderUnavailableError` when the call did not complete and
        `ProviderResponseError` when it completed with something unusable.
        """


@runtime_checkable
class VisionProvider(Protocol):
    """Describe a single image as a JSON document.

    Frames arrive as a data URL because that is what the current call site builds
    after enforcing its own size ceiling; keeping that shape means the size limit
    stays where the file is read rather than being re-implemented per provider.
    """

    @property
    def name(self) -> str:
        """Stable identifier recorded alongside the frame analysis."""

    def describe_image_json(self, *, system: str, prompt: str, image_data_url: str) -> str:
        """Return the model's description as raw JSON text."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turn texts into vectors for hybrid retrieval.

    Order matters: the caller pairs vectors with the texts it sent, so an
    implementation must return them in the input order and must not silently
    drop or reorder entries. Returning a different count is a
    `ProviderResponseError`, not a partial success.
    """

    @property
    def name(self) -> str:
        """Stable identifier recorded with a cached embedding bundle."""

    @property
    def dimensions(self) -> int:
        """Vector width, so a cache can reject a bundle built by another model."""

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one vector per input text, in the same order."""
