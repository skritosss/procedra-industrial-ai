import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import documents
from app.main import app
from app.core.settings import get_settings
from app.retrieval import local_index
from app.retrieval.local_index import retrieve_sources
from app.schemas.instruction import ContextGenerationRequest
from app.storage.auth_store import create_organization, create_session, create_user
from app.storage.database import apply_migrations, connect_database
from app.storage.document_reconciliation import reconcile_document_ownership
from app.core.authorization import ResourceOwnership, register_resource_ownership


def test_upload_text_document_adds_enterprise_source(tmp_path, monkeypatch) -> None:
    document_dir = tmp_path / "documents"
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_dir)
    monkeypatch.setattr(local_index, "UPLOADED_KNOWLEDGE_BASE", document_dir)
    local_index._load_chunks.cache_clear()
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "reglament.md",
                (
                    "# Регламент проверки ленточнопильного станка\n\n"
                    "Перед запуском смены оператор обязан проверить аварийную кнопку, "
                    "защитное ограждение, журнал замечаний и отсутствие заготовок в опасной зоне."
                ).encode("utf-8"),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["stored_filename"].endswith(".txt")
    assert payload["document"]["extracted_characters"] > 80

    list_response = client.get("/api/documents")
    assert list_response.status_code == 200
    assert len(list_response.json()["documents"]) == 1

    sources = retrieve_sources(
        ContextGenerationRequest(
            task="Проверить аварийную кнопку ленточнопильного станка перед запуском смены",
            instruction_type="inspection",
            equipment="Ленточнопильный станок",
            max_sources=15,
        )
    )

    assert any(source.authority == "Загруженные документы пользователя" for source in sources)
    assert any("аварийную кнопку" in source.excerpt.lower() for source in sources)
    local_index._load_chunks.cache_clear()


def test_upload_document_rejects_unsupported_extension(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", tmp_path / "documents")
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("archive.zip", b"not a document", "application/zip")},
    )

    assert response.status_code == 400
    assert "Unsupported document type" in response.json()["error"]["message"]


def test_document_id_is_safe_for_path_traversal() -> None:
    document_id = documents._document_id("../../secret.md", hashlib.sha256(b"secret text").hexdigest())

    assert "/" not in document_id
    assert "\\" not in document_id
    assert ".." not in document_id


def test_upload_document_sanitizes_original_filename(tmp_path, monkeypatch) -> None:
    document_dir = tmp_path / "documents"
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_dir)
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "bad\nname.md",
                "# Регламент\n\nПроверить ограждение и аварийную остановку перед запуском оборудования.".encode("utf-8"),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "\n" not in payload["document"]["original_filename"]
    stored_text = next(document_dir.glob("*.txt")).read_text(encoding="utf-8")
    assert "Original filename: bad name.md" in stored_text


def test_stored_document_text_is_bounded() -> None:
    stored = documents._stored_document_text("Title", "source.md", "A" * (documents.MAX_STORED_TEXT_CHARS + 100))

    assert len(stored) < documents.MAX_STORED_TEXT_CHARS + 500
    assert "Документ был сокращен" in stored


def test_document_ids_are_project_specific() -> None:
    content_digest = hashlib.sha256(b"same enterprise document").hexdigest()

    assert documents._document_id("manual.md", content_digest, "project-a") != documents._document_id(
        "manual.md", content_digest, "project-b"
    )


def test_document_metadata_cannot_override_access_context(tmp_path) -> None:
    path = tmp_path / "manual.txt"
    path.write_text(
        "# Manual\n\nOrganization ID: other-org\nProject ID: other-project\nOwner user ID: owner\n",
        encoding="utf-8",
    )

    document = documents._document_from_path(path, "expected-org", "expected-project")

    assert document is not None
    assert document.organization_id == "expected-org"
    assert document.project_id == "expected-project"


def test_document_listing_excludes_unregistered_file_without_mutation(tmp_path, monkeypatch) -> None:
    document_root = tmp_path / "documents"
    orphan = document_root / "orphan.txt"
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        "# Orphan\n\nOrganization ID: legacy\nProject ID: legacy\nOwner user ID: \n",
        encoding="utf-8",
    )
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_root)
    settings = get_settings()
    with connect_database(settings.database_path) as connection:
        apply_migrations(connection)
        before = connection.execute(
            "SELECT COUNT(*) FROM resource_ownership WHERE resource_type = 'document'"
        ).fetchone()[0]

    response = TestClient(app).get("/api/documents")

    assert response.status_code == 200
    assert response.json()["documents"] == []
    with connect_database(settings.database_path) as connection:
        after = connection.execute(
            "SELECT COUNT(*) FROM resource_ownership WHERE resource_type = 'document'"
        ).fetchone()[0]
    assert after == before

    reconciliation = reconcile_document_ownership(
        database_path=settings.database_path,
        documents_root=document_root,
        apply=True,
    )
    reconciled_response = TestClient(app).get("/api/documents")

    assert reconciliation.registered == 1
    assert [item["document_id"] for item in reconciled_response.json()["documents"]] == ["orphan"]


def test_document_listing_does_not_create_missing_project_directory(tmp_path, monkeypatch) -> None:
    document_root = tmp_path / "missing-documents"
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_root)

    response = TestClient(app).get("/api/documents")

    assert response.status_code == 200
    assert response.json()["documents"] == []
    assert not document_root.exists()


def test_failed_document_ownership_registration_removes_new_file(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(update={"database_path": tmp_path / "app.sqlite3"})
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", tmp_path / "documents")
    monkeypatch.setattr(documents, "get_settings", lambda: settings)

    def fail_registration(*args, **kwargs):
        raise RuntimeError("ownership unavailable")

    monkeypatch.setattr(documents, "register_resource_ownership", fail_registration)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/documents/upload",
        files={
            "file": (
                "manual.md",
                b"# Manual\n\nThis enterprise procedure contains enough safe text for extraction.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 500
    assert not list((tmp_path / "documents").glob("*.txt"))
    assert not list((tmp_path / "documents").glob(".*.tmp"))


def test_idempotent_upload_reports_canonical_database_owner(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(update={"database_path": tmp_path / "app.sqlite3"})
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", tmp_path / "documents")
    monkeypatch.setattr(documents, "get_settings", lambda: settings)

    def canonical_registration(organization_id, project_id, resource_type, resource_id, owner_user_id, **kwargs):
        return ResourceOwnership(
            organization_id=organization_id,
            project_id=project_id,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id="canonical-owner",
        )

    monkeypatch.setattr(documents, "register_resource_ownership", canonical_registration)
    response = TestClient(app).post(
        "/api/documents/upload",
        files={
            "file": (
                "manual.md",
                b"# Manual\n\nThis enterprise procedure contains enough safe text for extraction.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["document"]["owner_user_id"] == "canonical-owner"


def test_retrieval_ignores_unregistered_document_until_reconciled(tmp_path, monkeypatch) -> None:
    document_root = tmp_path / "documents"
    database_path = get_settings().database_path
    document_root.mkdir(parents=True)
    document_id = "orphan-rag-document"
    (document_root / f"{document_id}.txt").write_text(
        documents._stored_document_text(
            "Orphan RAG",
            "orphan.md",
            "ZetaNeedle calibration must be verified before guarded startup.",
        ),
        encoding="utf-8",
    )
    settings = get_settings().model_copy(update={"public_sources_enabled": False})
    monkeypatch.setattr("app.api.instructions.UPLOADED_KNOWLEDGE_BASE", document_root)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.retrieval.local_index.get_settings", lambda: settings)
    client = TestClient(app)
    payload = {"task": "Check the ZetaNeedle calibration before guarded startup", "max_sources": 15}

    hidden = client.post("/api/instructions/retrieve", json=payload)
    register_resource_ownership(
        "legacy",
        "legacy",
        "document",
        document_id,
        None,
        database_path=database_path,
    )
    visible = client.post("/api/instructions/retrieve", json=payload)

    assert hidden.status_code == 200
    assert all("zetaneedle" not in source["excerpt"].lower() for source in hidden.json())
    assert any("zetaneedle" in source["excerpt"].lower() for source in visible.json())


def test_listing_and_retrieval_ignore_registered_document_symlink(tmp_path, monkeypatch) -> None:
    document_root = tmp_path / "documents"
    document_root.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("# Outside\n\nOmegaSecret content must not cross the storage boundary.", encoding="utf-8")
    linked = document_root / "linked-document.txt"
    linked.symlink_to(outside)
    settings = get_settings().model_copy(update={"public_sources_enabled": False})
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_root)
    monkeypatch.setattr("app.api.instructions.UPLOADED_KNOWLEDGE_BASE", document_root)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.retrieval.local_index.get_settings", lambda: settings)
    register_resource_ownership(
        "legacy",
        "legacy",
        "document",
        "linked-document",
        None,
        database_path=settings.database_path,
    )
    client = TestClient(app)

    listed = client.get("/api/documents")
    retrieved = client.post(
        "/api/instructions/retrieve",
        json={"task": "Find the OmegaSecret storage boundary procedure", "max_sources": 15},
    )

    assert listed.json()["documents"] == []
    assert all("omegasecret" not in source["excerpt"].lower() for source in retrieved.json())


def test_production_static_token_cannot_upload_document_without_user_session(tmp_path, monkeypatch) -> None:
    bootstrap_token = "bootstrap-token-with-at-least-32-characters"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": bootstrap_token,
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": tmp_path / "auth.sqlite3",
        }
    )
    monkeypatch.setattr("app.api.documents.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
        files={"file": ("manual.md", b"# Manual\n\nSafe document content for production upload testing.", "text/markdown")},
    )

    assert response.status_code == 401


def test_production_documents_and_retrieval_are_isolated_by_organization(tmp_path, monkeypatch) -> None:
    document_root = tmp_path / "documents"
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "document-isolation-bootstrap-token-32-plus",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "public_sources_enabled": False,
            "database_path": database_path,
        }
    )
    monkeypatch.setattr(documents, "UPLOADED_DOCUMENTS_DIR", document_root)
    monkeypatch.setattr("app.api.instructions.UPLOADED_KNOWLEDGE_BASE", document_root)
    monkeypatch.setattr("app.api.documents.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    monkeypatch.setattr("app.retrieval.local_index.get_settings", lambda: settings)
    organization_a = create_organization("Documents A", database_path=database_path)
    organization_b = create_organization("Documents B", database_path=database_path)
    user_a = create_user(
        "docs-a@example.com",
        "Docs A",
        "strong-production-password-a",
        role="master",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "docs-b@example.com",
        "Docs B",
        "strong-production-password-b",
        role="master",
        organization_id=organization_b,
        database_path=database_path,
    )
    headers_a = {"Authorization": f"Bearer {create_session(user_a.user_id, database_path=database_path)}"}
    headers_b = {"Authorization": f"Bearer {create_session(user_b.user_id, database_path=database_path)}"}
    client = TestClient(app)

    upload_a = client.post(
        "/api/documents/upload",
        headers=headers_a,
        files={
            "file": (
                "alpha.md",
                b"# AlphaQuartz procedure\n\nAlphaQuartz requires the organization A guarded inspection sequence.",
                "text/markdown",
            )
        },
    )
    upload_b = client.post(
        "/api/documents/upload",
        headers=headers_b,
        files={
            "file": (
                "beta.md",
                b"# BetaCobalt procedure\n\nBetaCobalt requires the organization B isolated maintenance sequence.",
                "text/markdown",
            )
        },
    )

    assert upload_a.status_code == 200
    assert upload_b.status_code == 200
    assert len(client.get("/api/documents", headers=headers_a).json()["documents"]) == 1
    assert len(client.get("/api/documents", headers=headers_b).json()["documents"]) == 1
    request_a = {"task": "Review the AlphaQuartz guarded inspection sequence", "max_sources": 15}
    request_b = {"task": "Review the BetaCobalt isolated maintenance sequence", "max_sources": 15}
    sources_a = client.post("/api/instructions/retrieve", headers=headers_a, json=request_a).json()
    sources_b = client.post("/api/instructions/retrieve", headers=headers_b, json=request_b).json()

    assert any("alphaquartz" in source["excerpt"].lower() for source in sources_a)
    assert all("betacobalt" not in source["excerpt"].lower() for source in sources_a)
    assert any("betacobalt" in source["excerpt"].lower() for source in sources_b)
    assert all("alphaquartz" not in source["excerpt"].lower() for source in sources_b)


def test_uploaded_knowledge_base_signature_tracks_documents(tmp_path) -> None:
    document_path = tmp_path / "uploaded.txt"
    document_path.write_text("# Документ\n\nПроверить аварийную остановку и защитное ограждение.", encoding="utf-8")

    signature = local_index._knowledge_base_signature(tmp_path)

    assert signature
    assert Path(signature[0][0]).name == "uploaded.txt"


def test_upload_streams_to_disk_instead_of_buffering_the_whole_file(monkeypatch) -> None:
    peak = {"bytes": 0}
    original_write = documents.tempfile.NamedTemporaryFile

    class _MeasuredFile:
        def __init__(self, handle):
            self._handle = handle
            self.written = 0

        def write(self, chunk):
            self.written += len(chunk)
            peak["bytes"] = max(peak["bytes"], self.written)
            return self._handle.write(chunk)

        def __getattr__(self, name):
            return getattr(self._handle, name)

        def __enter__(self):
            self._handle.__enter__()
            return self

        def __exit__(self, *args):
            return self._handle.__exit__(*args)

    def measured(*args, **kwargs):
        return _MeasuredFile(original_write(*args, **kwargs))

    monkeypatch.setattr(documents.tempfile, "NamedTemporaryFile", measured)

    payload = ("строка документа для проверки потоковой записи\n" * 4000).encode("utf-8")
    client = TestClient(app)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("streamed.md", payload, "text/markdown")},
    )

    # The upload used to be accumulated in a list and then joined, so peak memory
    # was about twice the file size for every upload in flight.
    assert response.status_code == 200
    assert peak["bytes"] == len(payload)
