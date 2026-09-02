"""A model that fails must not look like a model that was never configured.

Both produce the same response, with the same `deterministic` mode on screen.
Without these lines an operator has nothing to tell the two apart.
"""

import logging

import pytest

from app.generation.pipeline import generate_instruction
from app.providers.errors import ProviderError
from app.schemas.instruction import InstructionRequest


REQUEST = InstructionRequest(
    task="Подготовить рабочее место оператора перед запуском пресса",
    industry_profile="manufacturing",
    instruction_type="workplace_preparation",
)


def _enable_model(monkeypatch) -> None:
    from app.generation import pipeline

    settings = pipeline.get_settings().model_copy(
        update={"openai_enabled": True, "openai_api_key": "test-key"}
    )
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)


def test_a_failing_text_provider_is_reported(monkeypatch, caplog) -> None:
    from app.generation import pipeline

    _enable_model(monkeypatch)
    monkeypatch.setattr(pipeline, "text_provider", lambda settings: object())

    def explode(**_kwargs):
        raise ProviderError("openai", "upstream returned 503")

    monkeypatch.setattr(pipeline, "_generate_with_model", explode)

    with caplog.at_level(logging.WARNING, logger="industrial_ai.perimeter"):
        response = generate_instruction(REQUEST)

    assert response.generation_mode == "deterministic"
    records = [r for r in caplog.records if r.name == "industrial_ai.perimeter"]
    assert records, "сбой модели не оставил следа в логе"
    assert records[0].capability == "text"
    assert "ProviderError" in records[0].reason


def test_a_deployment_without_a_model_is_not_reported(monkeypatch, caplog) -> None:
    """The quiet path must stay quiet: a deterministic deployment is not a fault."""
    from app.generation import pipeline

    monkeypatch.setattr(pipeline, "text_provider", lambda settings: None)

    with caplog.at_level(logging.WARNING, logger="industrial_ai.perimeter"):
        response = generate_instruction(REQUEST)

    assert response.generation_mode == "deterministic"
    assert not [r for r in caplog.records if r.name == "industrial_ai.perimeter"]


def test_a_failing_embedding_provider_is_reported(monkeypatch, caplog) -> None:
    from app.retrieval import local_index

    settings = local_index.get_settings().model_copy(
        update={"openai_enabled": True, "openai_api_key": "test-key"}
    )
    monkeypatch.setattr(local_index, "get_settings", lambda: settings)

    def explode(_texts):
        raise ProviderError("openai", "embedding endpoint refused the request")

    monkeypatch.setattr(local_index, "_model_embeddings", explode)

    with caplog.at_level(logging.WARNING, logger="industrial_ai.perimeter"):
        _query, _chunks, mode = local_index._embedding_bundle("подготовка места", ())

    assert mode == "deterministic"
    records = [r for r in caplog.records if r.name == "industrial_ai.perimeter"]
    assert records, "сбой эмбеддингов не оставил следа в логе"
    assert records[0].capability == "embedding"


def test_a_mistake_in_our_own_code_is_not_absorbed(monkeypatch) -> None:
    """AttributeError is not a provider fault. Catching it turned a bug in this
    module into quietly worse retrieval, which is the hardest kind to notice."""
    from app.retrieval import local_index

    settings = local_index.get_settings().model_copy(
        update={"openai_enabled": True, "openai_api_key": "test-key"}
    )
    monkeypatch.setattr(local_index, "get_settings", lambda: settings)

    def explode(_texts):
        raise AttributeError("'NoneType' object has no attribute 'data'")

    monkeypatch.setattr(local_index, "_model_embeddings", explode)

    with pytest.raises(AttributeError):
        local_index._embedding_bundle("подготовка места", ())
