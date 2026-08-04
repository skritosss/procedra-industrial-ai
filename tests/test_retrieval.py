import pytest
from pydantic import ValidationError

from app.retrieval import local_index
from app.retrieval.local_index import build_context_from_sources, retrieve_sources
from app.retrieval.public_sources import PUBLIC_SOURCE_CATALOG, retrieve_public_sources
from app.schemas.instruction import ContextGenerationRequest, RetrievedSource


def test_retrieved_source_rejects_non_http_external_url() -> None:
    with pytest.raises(ValidationError, match="HTTP or HTTPS"):
        RetrievedSource(
            source_id="unsafe",
            title="Unsafe",
            path="public://unsafe",
            chunk_index=0,
            score=1,
            excerpt="Unsafe source",
            source_type="public",
            url="javascript:alert(1)",
        )


def test_retrieve_sources_finds_relevant_documentation() -> None:
    request = ContextGenerationRequest(
        task="Подготовить рабочее место оператора перед запуском оборудования",
        instruction_type="workplace_preparation",
        department="Кузнечно-прессовый участок",
        equipment="Рабочее место оператора",
        technical_context="Проверить защитные ограждения, аварийную остановку и отсутствие посторонних предметов.",
    )

    sources = retrieve_sources(request)

    assert sources
    assert sources[0].source_type == "public"
    assert any("рабоч" in source.excerpt.lower() or "огражд" in source.excerpt.lower() for source in sources)
    assert sources[0].score > 0
    assert sources[0].influence_score > 0
    assert any(source.matched_terms for source in sources)
    assert any(source.source_type == "public" and source.url for source in sources)
    assert any(source.source_id == "workplace_preparation" for source in sources)


def test_build_context_from_sources_includes_source_ids() -> None:
    request = ContextGenerationRequest(
        task="Остановить оборудование и передать смену",
        instruction_type="equipment_shutdown",
    )
    sources = retrieve_sources(request)

    context = build_context_from_sources(sources)

    assert context
    assert "[" in context
    assert "Почему выбран:" in context
    assert "Тип документа:" in context
    assert "Профили применимости:" in context


def test_retrieve_sources_respects_max_sources() -> None:
    request = ContextGenerationRequest(
        task="Подготовить рабочее место оператора перед запуском оборудования",
        instruction_type="workplace_preparation",
        max_sources=2,
    )

    sources = retrieve_sources(request)

    assert len(sources) <= 2


def test_public_sources_rank_safety_and_standards_for_equipment_request() -> None:
    request = ContextGenerationRequest(
        task="Подготовить инструкцию по безопасному запуску производственного оборудования",
        instruction_type="equipment_startup",
        equipment="Ленточнопильный станок",
        max_sources=3,
    )

    sources = retrieve_public_sources(request, max_sources=3)

    assert sources
    assert all(source.source_type == "public" for source in sources)
    assert all(source.url for source in sources)
    assert all(0 < source.influence_score <= 1 for source in sources)
    assert any(source.matched_terms for source in sources)
    assert all(source.authority for source in sources)
    assert all(source.document_type for source in sources)
    assert all(source.contribution_reason for source in sources)
    assert any("manufacturing" in source.applicable_profiles for source in sources)
    combined = " ".join(source.title + " " + source.excerpt for source in sources).lower()
    assert "гост" in combined or "технический регламент" in combined or "охране труда" in combined


def test_public_catalog_has_partner_demo_source_depth() -> None:
    assert len(PUBLIC_SOURCE_CATALOG) >= 15
    assert len({source.source_id for source in PUBLIC_SOURCE_CATALOG}) == len(PUBLIC_SOURCE_CATALOG)
    assert all(source.url.startswith("https://") for source in PUBLIC_SOURCE_CATALOG)
    assert all(source.authority and source.document_type and source.excerpt for source in PUBLIC_SOURCE_CATALOG)


def test_public_sources_use_industry_profile_for_ranking() -> None:
    request = ContextGenerationRequest(
        task="Подготовить инструкцию по безопасной проверке строительной площадки перед началом работ",
        instruction_type="inspection",
        industry_profile="construction",
        technical_context="Проверить ограждение зоны работ, СИЗ, пожарные риски и порядок допуска.",
        max_sources=5,
    )

    sources = retrieve_public_sources(request, max_sources=5)

    assert sources
    assert any("construction" in source.applicable_profiles for source in sources[:3])
    assert all(source.contribution_reason for source in sources)
    assert any("отраслевым профилем" in source.contribution_reason for source in sources)


def test_public_sources_infer_additional_market_profiles() -> None:
    education_request = ContextGenerationRequest(
        task="Составить инструкцию для обучения нового сотрудника и проверки знаний",
        instruction_type="training",
        industry_profile="education",
        max_sources=5,
    )
    public_service_request = ContextGenerationRequest(
        task="Описать нормативную процедуру проверки и распределения ответственности",
        instruction_type="general",
        industry_profile="public_service",
        max_sources=5,
    )

    education_sources = retrieve_public_sources(education_request, max_sources=5)
    public_service_sources = retrieve_public_sources(public_service_request, max_sources=5)

    assert any("education" in source.applicable_profiles for source in education_sources)
    assert any("public_service" in source.applicable_profiles for source in public_service_sources)


def test_retrieved_source_cleans_metadata_and_deduplicates_profiles() -> None:
    source = RetrievedSource(
        source_id="test",
        title="Test",
        path="test.md",
        chunk_index=0,
        score=1,
        excerpt="Excerpt",
        authority="   ",
        document_type="  ГОСТ  ",
        applicable_profiles=["general", "general", "manufacturing"],
        contribution_reason="  Reason  ",
    )

    assert source.authority is None
    assert source.document_type == "ГОСТ"
    assert source.contribution_reason == "Reason"
    assert source.applicable_profiles == ["general", "manufacturing"]


def test_retrieve_sources_defaults_to_external_majority() -> None:
    request = ContextGenerationRequest(
        task="Подготовить инструкцию по безопасному запуску производственного оборудования",
        instruction_type="equipment_startup",
        equipment="Ленточнопильный станок",
        technical_context="Проверить ограждения, аварийную остановку, СИЗ, пожарные риски и условия труда.",
    )

    sources = retrieve_sources(request)
    public_count = sum(1 for source in sources if source.source_type == "public")

    assert len(sources) <= 15
    assert public_count > len(sources) / 2
    assert sources[0].source_type == "public"
    assert sources[0].influence_score > 0
    assert any("Нормативный статус" in source.excerpt for source in sources if source.source_type == "public")


def test_retrieve_sources_can_disable_public_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        local_index,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "public_sources_enabled": False,
                "public_sources_max_results": 15,
            },
        )(),
    )
    request = ContextGenerationRequest(
        task="Подготовить рабочее место оператора перед запуском оборудования",
        instruction_type="workplace_preparation",
        max_sources=4,
    )

    sources = retrieve_sources(request)

    assert sources
    assert all(source.source_type == "local" for source in sources)
    assert all(source.document_type == "Локальный технический документ" for source in sources)
    assert all(source.contribution_reason for source in sources)


def test_retrieve_sources_can_rank_by_embedding_similarity_without_keyword_overlap(monkeypatch, tmp_path) -> None:
    (tmp_path / "alpha.md").write_text("# Alpha\nred valve manual", encoding="utf-8")
    (tmp_path / "beta.md").write_text("# Beta\nblue pump manual", encoding="utf-8")

    def fake_embedding_bundle(query, chunks):
        embeddings = {}
        for chunk in chunks:
            key = (str(chunk.path), chunk.chunk_index)
            embeddings[key] = (1.0, 0.0) if chunk.source_id == "beta" else (0.0, 1.0)
        return (1.0, 0.0), embeddings, "openai"

    monkeypatch.setattr(local_index, "_embedding_bundle", fake_embedding_bundle)
    monkeypatch.setattr(
        local_index,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "public_sources_enabled": False,
                "public_sources_max_results": 15,
            },
        )(),
    )
    request = ContextGenerationRequest(task="zzzzzzzzzz semantic-only request")

    sources = retrieve_sources(request, knowledge_base=tmp_path)

    assert sources
    assert sources[0].source_id == "beta"


def test_retrieve_sources_reload_when_knowledge_base_file_changes(tmp_path) -> None:
    document = tmp_path / "process.md"
    document.write_text("# Процесс\nпервичный контроль инструмента", encoding="utf-8")
    request = ContextGenerationRequest(task="Проверить инструмент перед работой")

    first_sources = retrieve_sources(request, knowledge_base=tmp_path)
    document.write_text("# Процесс\nпроверить аварийную остановку и ограждение", encoding="utf-8")
    second_sources = retrieve_sources(request, knowledge_base=tmp_path)

    assert first_sources
    assert second_sources
    assert any("первичный" in source.excerpt for source in first_sources)
    assert any("аварийную остановку" in source.excerpt for source in second_sources)


def test_retrieve_sources_uses_safe_path_for_external_knowledge_base(tmp_path) -> None:
    (tmp_path / "external.md").write_text("# External\nпроверить ограждение", encoding="utf-8")

    sources = retrieve_sources(
        ContextGenerationRequest(task="Проверить ограждение перед запуском", max_sources=15),
        knowledge_base=tmp_path,
    )

    assert any(source.path == "external.md" for source in sources)


def test_retrieve_sources_excerpt_focuses_on_relevant_sentence_in_long_chunk(tmp_path) -> None:
    filler = " ".join(["общий производственный ввод"] * 80)
    (tmp_path / "long.md").write_text(
        "# Long\n"
        f"{filler}. "
        "Перед запуском проверить аварийную остановку, защитные ограждения и журнал смены. "
        f"{filler}.",
        encoding="utf-8",
    )

    sources = retrieve_sources(
        ContextGenerationRequest(task="Проверить аварийную остановку и ограждения перед запуском"),
        knowledge_base=tmp_path,
    )

    assert sources
    local_source = next(source for source in sources if source.source_type == "local")
    assert "аварийную остановку" in local_source.excerpt
    assert "защитные ограждения" in local_source.excerpt
    assert len(local_source.excerpt) <= 520


def test_retrieve_sources_skips_invalid_utf8_documents(tmp_path) -> None:
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00")
    (tmp_path / "good.md").write_text("# Good\nпроверить ограждение", encoding="utf-8")

    sources = retrieve_sources(
        ContextGenerationRequest(task="Проверить ограждение перед запуском"),
        knowledge_base=tmp_path,
    )

    assert sources
    assert any(source.source_id == "good" for source in sources)


def test_embedding_bundle_falls_back_to_local_when_openai_embedding_fails(monkeypatch, tmp_path) -> None:
    (tmp_path / "doc.md").write_text("# Doc\nпроверить ограждение", encoding="utf-8")
    chunks = local_index._load_chunks(str(tmp_path), local_index._knowledge_base_signature(tmp_path))
    monkeypatch.setattr(
        local_index,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": True,
                "openai_api_key": "test",
                "openai_embedding_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    monkeypatch.setattr(local_index, "_model_embeddings", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad")))

    query_embedding, chunk_embeddings, mode = local_index._embedding_bundle("проверить ограждение", chunks)

    assert mode == "deterministic"
    assert query_embedding
    assert chunk_embeddings
