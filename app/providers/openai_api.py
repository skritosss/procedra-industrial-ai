"""Any endpoint that speaks the OpenAI protocol.

Not "OpenAI the company". The SDK accepts a `base_url`, so one implementation
reaches the hosted API, Russian providers exposing a compatible endpoint,
self-hosted vLLM, Ollama and llama.cpp inside a plant perimeter, and whatever
corporate LLM gateway a customer already runs. That is the whole reason ADR-0001
chose a compatible provider over a class per vendor.

This module is the only place in the application allowed to import the vendor
SDK, and a test enforces that rather than a convention.
"""

from __future__ import annotations

from collections.abc import Sequence
from json import JSONDecodeError

from openai import OpenAI, OpenAIError
from openai.types.responses import EasyInputMessageParam, ResponseTextConfigParam

from app.providers.errors import (
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnavailableError,
)


def _build_client(*, api_key: str | None, base_url: str | None, timeout: float, provider: str) -> OpenAI:
    if not api_key:
        raise ProviderNotConfiguredError(provider, "no API key configured")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return OpenAI(api_key=api_key, timeout=timeout)


class OpenAICompatibleTextProvider:
    """Structured text completion through the responses API."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout: float,
        base_url: str | None = None,
        name: str = "openai_api",
    ) -> None:
        self._name = name
        self._model = model
        self._client = _build_client(
            api_key=api_key, base_url=base_url, timeout=timeout, provider=name
        )

    @property
    def name(self) -> str:
        return self._name

    def complete_json(self, *, system: str, prompt: str) -> str:
        try:
            text_config: ResponseTextConfigParam = {"format": {"type": "json_object"}}
            response = self._client.responses.create(
                model=self._model,
                instructions=system,
                input=prompt,
                text=text_config,
            )
        except OpenAIError as error:
            raise ProviderUnavailableError(self._name, str(error)) from error
        output = getattr(response, "output_text", None)
        if not output:
            raise ProviderResponseError(self._name, "empty response")
        return str(output)


class OpenAICompatibleVisionProvider:
    """Single-image description through the same responses API."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout: float,
        base_url: str | None = None,
        name: str = "openai_api",
    ) -> None:
        self._name = name
        self._model = model
        self._client = _build_client(
            api_key=api_key, base_url=base_url, timeout=timeout, provider=name
        )

    @property
    def name(self) -> str:
        return self._name

    def describe_image_json(self, *, system: str, prompt: str, image_data_url: str) -> str:
        message: EasyInputMessageParam = {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_data_url, "detail": "auto"},
            ],
        }
        text_config: ResponseTextConfigParam = {"format": {"type": "json_object"}}
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=system,
                input=[message],
                text=text_config,
            )
        except OpenAIError as error:
            raise ProviderUnavailableError(self._name, str(error)) from error
        output = getattr(response, "output_text", None)
        if not output:
            raise ProviderResponseError(self._name, "empty response")
        return str(output)


class OpenAICompatibleEmbeddingProvider:
    """Embeddings, returned strictly in the order they were requested."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout: float,
        dimensions: int,
        base_url: str | None = None,
        name: str = "openai_api",
    ) -> None:
        self._name = name
        self._model = model
        self._dimensions = dimensions
        self._client = _build_client(
            api_key=api_key, base_url=base_url, timeout=timeout, provider=name
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        try:
            response = self._client.embeddings.create(model=self._model, input=list(texts))
        except (OpenAIError, JSONDecodeError) as error:
            raise ProviderUnavailableError(self._name, str(error)) from error
        try:
            ordered = sorted(response.data, key=lambda item: item.index)
        except (AttributeError, TypeError) as error:
            raise ProviderResponseError(self._name, "malformed embedding payload") from error
        if len(ordered) != len(texts):
            # The caller zips these with its inputs, so a short answer is a wrong
            # answer rather than a partial one.
            raise ProviderResponseError(
                self._name, f"expected {len(texts)} vectors, received {len(ordered)}"
            )
        return tuple(tuple(float(value) for value in item.embedding) for item in ordered)
