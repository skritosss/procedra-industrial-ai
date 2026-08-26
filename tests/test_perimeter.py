import ipaddress
import logging

import pytest

from app.core.settings import Settings
from app.generation import pipeline
from app.providers import perimeter
from app.providers.errors import ProviderEgressBlockedError
from app.providers.registry import text_provider
from app.schemas.instruction import InstructionRequest


def _settings(**overrides) -> Settings:
    base = {
        "deployment_mode": "demo",
        "openai_enabled": True,
        "openai_api_key": "present",
        "llm_allow_external_calls": False,
        "llm_base_url": "http://127.0.0.1:8080/v1",
    }
    base.update(overrides)
    return Settings(**base)


def _resolver(monkeypatch, mapping: dict[str, list[str]]) -> None:
    """Answer host lookups from a table so no test touches DNS."""

    def fake(hostname: str, port: int, resolver=None):
        try:
            return {ipaddress.ip_address(hostname)}
        except ValueError:
            pass
        if resolver is not None:
            # The startup check passes a resolver that refuses to look names up;
            # the double has to honour that or it would test a different rule.
            raise OSError("name lookup not attempted")
        if hostname not in mapping:
            raise OSError(f"unknown host {hostname}")
        return {ipaddress.ip_address(address) for address in mapping[hostname]}

    monkeypatch.setattr(perimeter, "resolve_host_addresses", fake)


def test_startup_refuses_an_empty_endpoint_when_the_perimeter_is_closed() -> None:
    with pytest.raises(ValueError, match="LLM_BASE_URL must be set"):
        _settings(llm_base_url=None)


def test_startup_refuses_a_literal_public_endpoint() -> None:
    with pytest.raises(ValueError, match="public address"):
        _settings(llm_base_url="https://8.8.8.8/v1")


def test_startup_accepts_endpoints_inside_the_perimeter() -> None:
    assert _settings(llm_base_url="http://10.20.0.9:8000/v1").llm_base_url
    assert _settings(llm_base_url="http://127.0.0.1:8080/v1").llm_base_url


def test_startup_does_not_judge_a_hostname() -> None:
    """DNS may be down at boot, and refusing to start would also take the
    deterministic path down. The provider layer decides per call instead."""
    assert _settings(llm_base_url="https://vllm.plant.local/v1").llm_base_url


def test_provider_is_refused_when_the_endpoint_resolves_outside(monkeypatch) -> None:
    _resolver(monkeypatch, {"gateway.example.com": ["93.184.216.34"]})
    settings = _settings(llm_base_url="https://gateway.example.com/v1")
    with pytest.raises(ProviderEgressBlockedError, match="public address"):
        text_provider(settings)


def test_provider_is_built_when_the_endpoint_resolves_inside(monkeypatch) -> None:
    _resolver(monkeypatch, {"vllm.plant.local": ["10.4.0.7"]})
    assert text_provider(_settings(llm_base_url="https://vllm.plant.local/v1")) is not None


def test_an_unresolvable_endpoint_is_refused(monkeypatch) -> None:
    """Unknown is not the same as internal: a check that passes on "cannot tell"
    is not a check."""
    _resolver(monkeypatch, {})
    with pytest.raises(ProviderEgressBlockedError, match="does not resolve"):
        text_provider(_settings(llm_base_url="https://vllm.plant.local/v1"))


def test_an_open_perimeter_allows_a_public_endpoint(monkeypatch) -> None:
    _resolver(monkeypatch, {"api.vendor.example": ["93.184.216.34"]})
    settings = _settings(llm_allow_external_calls=True, llm_base_url="https://api.vendor.example/v1")
    assert text_provider(settings) is not None


def test_a_blocked_call_still_answers_and_is_recorded(monkeypatch, caplog) -> None:
    """The draft is produced deterministically. Silence would leave an operator
    unable to tell a closed perimeter from an unreachable model."""
    _resolver(monkeypatch, {"gateway.example.com": ["93.184.216.34"]})
    settings = _settings(llm_base_url="https://gateway.example.com/v1")
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)

    with caplog.at_level(logging.ERROR, logger="industrial_ai.perimeter"):
        response = pipeline.generate_instruction(
            InstructionRequest(task="Подготовить рабочее место оператора перед запуском оборудования")
        )

    assert response.generation_mode == "deterministic"
    assert response.instruction.steps
    assert any("perimeter" in record.message or "perimeter" in str(record.__dict__) for record in caplog.records)
