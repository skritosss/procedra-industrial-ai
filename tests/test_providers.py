from collections.abc import Sequence

import pytest

from app.providers import (
    EmbeddingProvider,
    ProviderEgressBlockedError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnavailableError,
    TextProvider,
    VisionProvider,
)


class _Text:
    name = "stub-text"

    def complete_json(self, *, system: str, prompt: str) -> str:
        return '{"ok": true}'


class _Vision:
    name = "stub-vision"

    def describe_image_json(self, *, system: str, prompt: str, image_data_url: str) -> str:
        return '{"summary": "кадр"}'


class _Embeddings:
    name = "stub-embeddings"
    dimensions = 3

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((float(len(text)), 0.0, 1.0) for text in texts)


def test_a_plain_class_satisfies_the_protocols_without_inheriting() -> None:
    # Structural typing is the point: a provider written against a corporate
    # gateway must not have to import our base classes to be usable.
    assert isinstance(_Text(), TextProvider)
    assert isinstance(_Vision(), VisionProvider)
    assert isinstance(_Embeddings(), EmbeddingProvider)


def test_missing_methods_do_not_satisfy_the_protocols() -> None:
    class Incomplete:
        name = "incomplete"

    assert not isinstance(Incomplete(), TextProvider)
    assert not isinstance(Incomplete(), VisionProvider)
    assert not isinstance(Incomplete(), EmbeddingProvider)


def test_embeddings_return_one_vector_per_text_in_order() -> None:
    provider = _Embeddings()
    vectors = provider.embed(["a", "bb", "ccc"])

    # The caller zips these with the texts it sent, so order and count are part
    # of the contract rather than an implementation detail.
    assert len(vectors) == 3
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0]
    assert all(len(vector) == provider.dimensions for vector in vectors)


@pytest.mark.parametrize(
    "error_type",
    [
        ProviderNotConfiguredError,
        ProviderUnavailableError,
        ProviderResponseError,
        ProviderEgressBlockedError,
    ],
)
def test_every_provider_error_is_catchable_as_one_hierarchy(error_type) -> None:
    # Call sites today catch a growing tuple of vendor exception classes. The
    # point of this hierarchy is that they can catch exactly one thing.
    with pytest.raises(ProviderError):
        raise error_type("stub", "boom")


def test_provider_errors_name_the_provider_that_failed() -> None:
    error = ProviderUnavailableError("openai_api", "timed out after 10s")

    assert error.provider == "openai_api"
    assert "openai_api" in str(error)
    assert "timed out after 10s" in str(error)


def test_provider_package_exports_no_vendor_sdk() -> None:
    import app.providers as providers

    # Stage 1.1 adds interfaces only. Anything that imports a vendor SDK arrives
    # in 1.2, and only inside this package.
    assert not hasattr(providers, "OpenAI")


def test_no_vendor_sdk_is_imported_outside_the_provider_package() -> None:
    import ast
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    provider_package = project_root / "app" / "providers"
    offenders: list[str] = []

    for path in sorted((project_root / "app").rglob("*.py")):
        if provider_package in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "openai" or name.startswith("openai.") for name in names):
                offenders.append(f"{path.relative_to(project_root)}:{node.lineno}")

    # ADR-0001 makes this a property of the codebase rather than a convention:
    # the point of the provider layer is that swapping the endpoint touches one
    # package. An import here is how that guarantee quietly rots.
    assert offenders == [], f"vendor SDK imported outside app/providers: {offenders}"


def _settings_with(**overrides):
    from app.core.settings import Settings

    base = {
        "openai_enabled": True,
        "openai_api_key": "test-key",
        "deployment_mode": "demo",
        "allow_unauthenticated_access": True,
    }
    return Settings(_env_file=None, **{**base, **overrides})


def test_a_custom_endpoint_reaches_every_provider() -> None:
    from app.providers.registry import embedding_provider, text_provider, vision_provider

    settings = _settings_with(llm_base_url="https://gateway.example.local/v1")

    # Without this the provider layer is vendor-neutral on paper and still only
    # able to talk to one company in practice: ADR-0001 exists so a plant can
    # point at its own endpoint.
    for build in (text_provider, vision_provider, embedding_provider):
        provider = build(settings)
        assert provider is not None
        assert str(provider._client.base_url).startswith("https://gateway.example.local")


def test_the_default_endpoint_is_left_to_the_sdk() -> None:
    from app.providers.registry import text_provider

    provider = text_provider(_settings_with(llm_base_url=None))

    assert provider is not None
    assert "openai.com" in str(provider._client.base_url)


def test_no_provider_is_built_without_a_model_configured() -> None:
    from app.providers.registry import embedding_provider, text_provider, vision_provider

    settings = _settings_with(openai_enabled=False)

    # This is the closed-perimeter guarantee in its simplest form: with nothing
    # configured, nothing in the provider layer can reach the network.
    assert text_provider(settings) is None
    assert vision_provider(settings) is None
    assert embedding_provider(settings) is None
