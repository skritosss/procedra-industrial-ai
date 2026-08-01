from pathlib import Path

from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.observability import runtime_metrics
from app.core.settings import get_settings
from app.api.instructions import _compact_video_context
from app.generation import pipeline
from app.main import app
from app.storage.auth_store import create_organization, create_session, create_user
from app.storage.metrics_store import initialize_metrics_store
from app.core.authorization import register_resource_ownership


def test_web_app_returns_language_switcher() -> None:
    client = TestClient(app)

    response = client.get("/")
    script_response = client.get("/static/app.js")
    style_response = client.get("/static/app.css")

    assert response.status_code == 200
    assert script_response.status_code == 200
    assert style_response.status_code == 200
    assert script_response.headers["content-type"].startswith("text/javascript")
    assert style_response.headers["content-type"].startswith("text/css")
    assert '<link rel="stylesheet" href="/static/app.css" />' in response.text
    assert '<script src="/static/app.js" defer></script>' in response.text
    assert "<style" not in response.text
    assert response.text.count("<script") == 1
    source = "\n".join((response.text, script_response.text, style_response.text))
    assert "Procedra" in source
    assert 'data-lang="ru"' in source
    assert 'data-lang="en"' in source
    assert 'data-result-view="sources"' in source
    assert 'data-result-view="editor"' in source
    assert 'data-result-view="execution"' in source
    assert '/static/assets/brand/procedra-wordmark-reversed.svg' in response.text
    assert '/static/assets/brand/procedra-favicon.svg' in response.text
    assert '/static/vendor/tabler-icons/file-pencil.svg' in response.text
    assert '/static/vendor/tabler-icons/edit.svg' in response.text
    assert '/static/vendor/tabler-icons/markdown.svg' in response.text
    assert '/static/vendor/tabler-icons/braces.svg' in response.text
    assert '/static/vendor/tabler-icons/chevron-left.svg' in response.text
    assert '/static/vendor/tabler-icons/menu-2.svg' in response.text
    assert '/static/vendor/tabler-icons/x.svg' in response.text
    assert 'id="use_context"' in source
    assert 'id="max_sources"' in source
    assert 'id="industry_profile"' in source
    assert 'id="sample_case"' in source
    assert 'id="sample-button"' in source
    assert 'id="export-markdown"' in source
    assert 'id="export-pdf"' in source
    assert 'id="export-json"' in source
    assert 'id="save-history"' in source
    assert 'id="improve-instruction"' in source
    assert 'aria-controls="result"' in source
    assert 'aria-labelledby="nav-instruction"' in source
    assert 'role="status"' in source
    assert 'role="region"' in source
    assert 'id="primary-sidebar"' in source
    assert 'id="mobile-menu-toggle"' in source
    assert 'id="sidebar-backdrop"' in source
    assert source.count('data-i18n-aria-label="nav') >= 11
    assert 'id="mobile-result-navigation"' not in source
    assert '<div class="tabs"' not in response.text
    assert "downloadTextFile" in source
    assert "downloadPdfFile" in source
    assert "export-pdf" in source
    assert "resultFilename" in source
    assert "protectedImageMarkup" in source
    assert "hydrateProtectedImages" in source
    assert 'data-protected-src=' in source
    assert "sampleCases" in source
    assert "operation template" in source.lower()
    assert "inspection_guarding" in source
    assert "maintenance_lockout" in source
    assert "construction_hot_work" in source
    assert "housing_utilities_gas" in source
    assert "security_phishing" in source
    assert "applyInstructionPayloadToForm" in source
    assert "resetProcessedVideoState" in source
    assert "syncContextControls" in source
    assert "generate-with-context" in source
    assert 'id="video_file"' in source
    assert 'id="document_file"' in source
    assert 'id="document-button"' in source
    assert 'id="document-list"' in source
    assert 'id="video_url"' in source
    assert 'id="visual_quality"' in source
    assert 'id="video-generate-button"' in source
    assert 'data-result-view="video"' in source
    assert 'data-result-view="history"' in source
    assert "/api/videos/jobs" in source
    assert 'id="video-job-progress"' in source
    assert 'id="video-cancel-button"' in source
    assert "videoStatusBothInputs" in source
    assert "generateFromVideoButton" in source
    assert "uploadDocument" in source
    assert "renderDocumentList" in source
    assert "/api/documents/upload" in source
    assert "/api/documents" in source
    assert "renderHistory" in source
    assert "saveCurrentInstructionVersion" in source
    assert "openHistoryVersion" in source
    assert "updateHistoryStatus" in source
    assert "currentAuditEvents" in source
    assert "renderAuditTrail" in source
    assert "auditTrailTitle" in source
    assert "Журнал аудита" in source
    assert 'id="workflow-modal"' in source
    assert 'id="workflow_reviewer_role"' in source
    assert "reviewer_role" in source
    assert "renderEditor" in source
    assert "renderExecution" in source
    assert "saveExecutionRun" in source
    assert "data-execution-action" in source
    assert "shopFloorMode" in source
    assert "toggle-shop-floor" in source
    assert "shop-floor-mode" in source
    assert "executionSummaryTitle" in source
    assert "/api/instructions/history/execution-summary" in source
    assert "rebuildEditedInstruction" in source
    assert "improveCurrentInstruction" in source
    assert "apiFetch" in source
    assert 'id="api_token"' in source
    assert "apiTokenInput" in source
    assert "authLogoutFailed" in source
    assert "response.status !== 401" in source
    assert 'apiFetch("/api/documents", {}, false)' in source
    assert "apiFetch(image.dataset.protectedSrc, {}, false)" in source
    assert "loadHistory(true)" in source
    assert "handleModalKeydown" in source
    assert 'event.key === "Escape"' in source
    assert 'event.key === "ArrowRight"' in source
    assert "workflowModalOpener" in source
    assert "/api/instructions/rebuild" in source
    assert "/api/instructions/improve" in source
    assert source.count("fetch(") == 1
    assert 'id="auth-modal"' in source
    assert 'id="auth_role"' in source
    assert "submitAuth" in source
    assert 'localStorage.removeItem("authAccessToken")' in source
    assert 'localStorage.removeItem("apiAccessToken")' in source
    assert 'localStorage.getItem("authAccessToken")' not in source
    assert 'localStorage.setItem("authAccessToken"' not in source
    assert 'localStorage.getItem("apiAccessToken")' not in source
    assert 'localStorage.setItem("apiAccessToken"' not in source
    assert 'credentials: "same-origin"' in source
    assert '"X-Auth-Transport": "cookie"' in source
    assert 'cookieValue("industrial_ai_csrf")' in source
    assert "const hasAuthenticatedUser = Boolean(currentUser)" in source
    assert 'const token = hasAuthenticatedUser ? "" : apiTokenInput.value.trim()' in source
    assert "headers.set(\"Authorization\", `Bearer ${token}`)" in source
    assert 'window.prompt(t("authTokenPrompt"), apiTokenInput.value.trim())' in source
    assert "!reviewerRoleValues.includes(currentUser.role)" in source
    assert "workflowReviewerInput.disabled = Boolean(currentUser)" in source
    assert "/api/auth/register" in source
    assert "/api/auth/login" in source
    assert "/api/auth/me" in source
    assert "history-status" in source
    assert "/workflow" in source
    assert "/api/instructions/history" in source
    assert "visualQualityDetailed" in source
    assert "applyVideoPayloadToForm" in source
    assert "Текстовый контекст из видео не найден" in source
    assert "frameAnalysisTitle" in source
    assert "renderFrameAnalyses" in source
    assert "videoSegmentsTitle" in source
    assert "renderVideoSegments" in source
    assert "generate-from-video" in source
    assert "compactVideoContext" in source
    assert "stepFrameLink" in source
    assert "renderStepFrameLink" in source
    assert "hasFrameAnalysisInContext" in source
    assert "frameSelectionScore" in source
    assert "frameSelectionReason" in source
    assert "videoStatusNoKeyframes" in source
    assert "Причина выбора" in source
    assert "Матрица ответственности" in source
    assert "Критерии приемки результата" in source
    assert "sourceExplanation" in source
    assert "sourceTypePublic" in source
    assert "sourceInfluence" in source
    assert "matchedTerms" in source
    assert "sourceAuthority" in source
    assert "sourceDocumentType" in source
    assert "sourceProfiles" in source
    assert "sourceContribution" in source
    assert 'rel="noopener noreferrer"' in source
    assert "formatProfiles" in source
    assert "translations[language].profiles[profile]" in source
    assert "riskLevel" in source
    assert "expertReview" in source
    assert "industryProfileLabel" in source
    assert "observedFacts" in source
    assert "localVerificationRequired" in source
    assert "expertReviewQuestions" in source
    assert "workflowStatus" in source
    assert "approvalRoles" in source
    assert "approvalBlockers" in source
    assert "workflowNextActions" in source
    assert "domain_risk_control" in source
    assert "request_focus" in source
    assert "source.url" in source
    assert 'lower.includes("подготов")' in source
    assert "item.loc.join" in source
    assert "JSON.stringify(item)" in source
    assert 'addEventListener("input", resetProcessedVideoState)' in source
    assert "videoGenerateButton.disabled = !(lastVideoPayload.keyframes" in source


def test_web_app_sets_basic_security_headers() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Response-Time-ms"]) >= 0
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    policy = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "script-src-attr 'none'" in policy
    assert "style-src 'self'" in policy
    assert "style-src-attr 'none'" in policy
    assert "object-src 'none'" in policy
    assert "base-uri 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "connect-src 'self'" in policy
    assert "img-src 'self' data: blob:" in policy
    assert "unsafe-inline" not in policy


def test_static_assets_receive_the_same_strict_csp() -> None:
    client = TestClient(app)

    script = client.get("/static/app.js")
    style = client.get("/static/app.css")

    assert script.status_code == 200
    assert style.status_code == 200
    assert "unsafe-inline" not in script.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in style.headers["Content-Security-Policy"]


def test_procedra_brand_and_vendored_icons_are_served_as_static_assets() -> None:
    client = TestClient(app)

    wordmark = client.get("/static/assets/brand/procedra-wordmark.svg")
    favicon = client.get("/static/assets/brand/procedra-favicon.svg")
    brand_png = client.get("/static/assets/brand/procedra-wordmark-monochrome.png")
    icon = client.get("/static/vendor/tabler-icons/file-pencil.svg")
    icon_license = client.get("/static/vendor/tabler-icons/LICENSE")

    assert wordmark.status_code == 200
    assert favicon.status_code == 200
    assert brand_png.status_code == 200
    assert icon.status_code == 200
    assert icon_license.status_code == 200
    assert wordmark.headers["content-type"].startswith("image/svg+xml")
    assert favicon.headers["content-type"].startswith("image/svg+xml")
    assert brand_png.headers["content-type"].startswith("image/png")
    assert icon.headers["content-type"].startswith("image/svg+xml")
    assert b"MIT License" in icon_license.content
    assert b"<text" not in wordmark.content
    assert b"http://www.w3.org/2000/svg" in wordmark.content
    for response in (wordmark, favicon, brand_png, icon, icon_license):
        assert "unsafe-inline" not in response.headers["Content-Security-Policy"]


def test_request_id_header_is_preserved() -> None:
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "demo-request-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "demo-request-1"


def test_auth_responses_are_not_cacheable() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"


def test_unsafe_request_id_header_is_replaced() -> None:
    client = TestClient(app)
    unsafe_request_id = "x" * 200

    response = client.get("/health", headers={"X-Request-ID": unsafe_request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != unsafe_request_id
    assert response.headers["X-Request-ID"]


def test_ready_endpoint_reports_minimal_public_status() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_details_requires_observability_access(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={"api_access_token": "secret-demo-token", "allow_unauthenticated_access": False}
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(app)

    unauthorized = client.get("/ready/details")
    authorized = client.get("/ready/details", headers={"Authorization": "Bearer secret-demo-token"})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "unauthorized"
    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["status"] == "ready"
    assert payload["deployment_mode"] in {"demo", "production"}
    assert isinstance(payload["openai_enabled"], bool)
    assert isinstance(payload["public_sources_enabled"], bool)
    assert payload["max_public_sources"] <= 15
    assert payload["document_max_bytes"] > 0
    assert isinstance(payload["api_auth_enabled"], bool)
    assert isinstance(payload["public_registration_enabled"], bool)
    assert isinstance(payload["role_self_assignment_enabled"], bool)
    assert payload["auth_session_ttl_seconds"] >= 300
    assert payload["auth_session_idle_timeout_seconds"] >= 300
    assert payload["auth_session_retention_seconds"] >= 3600
    assert isinstance(payload["rate_limit_enabled"], bool)
    assert payload["rate_limit_requests"] > 0
    assert payload["auth_rate_limit_requests"] > 0
    assert payload["metrics_public_enabled"] is False
    assert isinstance(payload["trust_proxy_headers"], bool)
    assert isinstance(payload["video_allowed_hosts"], list)
    assert payload["capabilities"]["model_generation"]["external_health"] == "not_probed"
    assert payload["capabilities"]["vision_analysis"]["mode"] in {
        "fallback_only",
        "configured_not_probed",
        "misconfigured_fallback",
    }
    assert payload["capabilities"]["public_source_catalog"]["mode"] in {
        "local_catalog",
        "disabled",
    }
    assert payload["generated_dir_writable"] is True
    assert payload["keyframes_dir_writable"] is True
    assert payload["instructions_dir_writable"] is True
    assert payload["uploads_dir_writable"] is True
    assert payload["documents_dir_writable"] is True
    assert payload["database_parent_writable"] is True
    assert payload["database_ready"] is True
    assert payload["metrics_database_ready"] is True


def test_observability_endpoints_accept_authenticated_user_session(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(
        update={
            "database_path": database_path,
            "metrics_database_path": tmp_path / "metrics.sqlite3",
        }
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_id = create_organization("Observability", database_path=database_path)
    user = create_user(
        "observability@example.com",
        "Observability User",
        "strong-observability-password",
        organization_id=organization_id,
        database_path=database_path,
    )
    session_token = create_session(user.user_id, database_path=database_path)
    initialize_metrics_store(settings.metrics_database_path)
    headers = {"Authorization": f"Bearer {session_token}"}
    client = TestClient(app)

    details = client.get("/ready/details", headers=headers)
    metrics = client.get("/metrics", headers=headers)

    assert details.status_code == 200
    assert metrics.status_code == 200


def test_public_metrics_flag_cannot_bypass_production_observability_auth(tmp_path, monkeypatch) -> None:
    static_token = "production-observability-token-at-least-32-characters"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": static_token,
            "allow_unauthenticated_access": False,
            "metrics_public_enabled": True,
            "database_path": tmp_path / "auth.sqlite3",
            "metrics_database_path": tmp_path / "metrics.sqlite3",
        }
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(app)

    unauthorized_metrics = client.get("/metrics")
    unauthorized_details = client.get("/ready/details")
    authorized_metrics = client.get("/metrics", headers={"Authorization": f"Bearer {static_token}"})

    assert unauthorized_metrics.status_code == 401
    assert unauthorized_details.status_code == 401
    assert authorized_metrics.status_code == 200


def test_ready_endpoint_reports_degraded_when_database_check_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.storage.auth_store.database_is_read_only", lambda database_path=None: False)
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded"}


def test_ready_endpoint_reports_degraded_when_metrics_database_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.storage.metrics_store.metrics_store_is_read_only_ready",
        lambda database_path: False,
    )
    client = TestClient(app)

    settings = get_settings().model_copy(update={"metrics_public_enabled": True})
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    response = client.get("/ready/details")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["metrics_database_ready"] is False


def test_metrics_endpoint_is_private_by_default() -> None:
    runtime_metrics.reset()
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_metrics_endpoint_reports_request_counters_when_public_enabled(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"metrics_public_enabled": True})
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    runtime_metrics.reset()
    client = TestClient(app)

    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_count"] >= 1
    assert payload["average_duration_ms"] >= 0
    assert payload["server_error_count"] >= 0
    assert "200" in payload["status_counts"]
    assert payload["durable"] is True
    assert payload["collector"]["status"] == "ready"
    assert payload["slo"]["availability"]["target_percent"] == 99.0
    assert payload["slo"]["latency"]["target_percent"] == 95.0


def test_metrics_backend_failure_is_visible_but_does_not_break_requests(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"metrics_public_enabled": True})
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.observability.record_request_metric", lambda *args, **kwargs: False)
    monkeypatch.setattr("app.core.observability.metrics_snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    runtime_metrics.reset()
    client = TestClient(app)

    health = client.get("/health")
    metrics_response = client.get("/metrics")

    assert health.status_code == 200
    assert metrics_response.status_code == 503
    payload = metrics_response.json()
    assert payload["collector"]["status"] == "unavailable"
    assert payload["alerts"] == [{"code": "metrics_backend_unavailable", "severity": "critical"}]
    assert payload["durable_write_failure_count"] >= 1


def test_validation_errors_use_stable_error_envelope() -> None:
    client = TestClient(app)

    response = client.post("/api/instructions/generate", json={"task": "short"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed"
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]
    assert payload["error"]["details"]
    assert payload["error"]["details"][0]["loc"]


def test_not_found_errors_use_stable_error_envelope() -> None:
    client = TestClient(app)

    response = client.get("/api/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]


def test_unhandled_errors_do_not_leak_details() -> None:
    route_path = "/__test_unhandled_error"
    if not any(getattr(route, "path", None) == route_path for route in app.routes):
        app.add_api_route(route_path, lambda: (_ for _ in ()).throw(RuntimeError("secret failure")), methods=["GET"])
    runtime_metrics.reset()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(route_path)

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "Internal server error"
    assert payload["error"]["details"] is None
    assert "secret failure" not in response.text
    assert runtime_metrics.snapshot()["server_error_count"] >= 1


def test_saved_instruction_json_is_not_public_static_file() -> None:
    client = TestClient(app)

    response = client.get("/generated/instructions/example-v1.json")

    assert response.status_code == 404


def test_api_auth_can_be_enabled_with_bearer_token(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={"api_access_token": "secret-demo-token", "allow_unauthenticated_access": False}
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    client = TestClient(app)

    unauthorized = client.post(
        "/api/instructions/generate",
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )
    authorized = client.post(
        "/api/instructions/generate",
        headers={"Authorization": "Bearer secret-demo-token"},
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "unauthorized"
    assert authorized.status_code == 200


def test_metrics_endpoint_respects_api_access_token(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={"api_access_token": "secret-demo-token", "allow_unauthenticated_access": False}
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(app)

    unauthorized = client.get("/metrics")
    authorized = client.get("/metrics", headers={"Authorization": "Bearer secret-demo-token"})

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "unauthorized"
    assert authorized.status_code == 200


def test_expensive_api_endpoints_are_rate_limited(monkeypatch) -> None:
    rate_limit.reset_rate_limit_state()
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_requests": 1,
            "rate_limit_window_seconds": 60,
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    client = TestClient(app)

    first = client.post(
        "/api/instructions/generate",
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )
    second = client.post(
        "/api/instructions/generate",
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"
    rate_limit.reset_rate_limit_state()


def test_rate_limit_ignores_forwarded_for_unless_trusted(monkeypatch) -> None:
    rate_limit.reset_rate_limit_state()
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_requests": 1,
            "rate_limit_window_seconds": 60,
            "trust_proxy_headers": False,
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    client = TestClient(app)

    first = client.post(
        "/api/instructions/generate",
        headers={"X-Forwarded-For": "203.0.113.1"},
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )
    second = client.post(
        "/api/instructions/generate",
        headers={"X-Forwarded-For": "203.0.113.2"},
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    rate_limit.reset_rate_limit_state()


def test_rate_limit_ignores_forwarded_for_from_untrusted_peer(monkeypatch) -> None:
    rate_limit.reset_rate_limit_state()
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_requests": 1,
            "rate_limit_window_seconds": 60,
            "trust_proxy_headers": True,
            "trusted_proxy_ips": ("127.0.0.1",),
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    client = TestClient(app)

    first = client.post(
        "/api/instructions/generate",
        headers={"X-Forwarded-For": "203.0.113.1"},
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )
    second = client.post(
        "/api/instructions/generate",
        headers={"X-Forwarded-For": "203.0.113.2"},
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    rate_limit.reset_rate_limit_state()


def test_generate_instruction_endpoint_returns_industrial_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate",
        json={
            "task": "Подготовить рабочее место оператора перед запуском оборудования",
            "user_level": "new_operator",
            "instruction_type": "workplace_preparation",
            "department": "Кузнечно-прессовый участок",
            "equipment": "Рабочее место оператора",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    instruction = payload["instruction"]
    assert payload["generation_mode"] == "fallback"
    assert instruction["required_ppe"]
    assert instruction["hazard_zones"]
    assert instruction["control_points"]
    assert instruction["observed_facts"]
    assert instruction["local_verification_required"]
    assert instruction["expert_review_questions"]
    assert instruction["workflow"]["status"] == "ai_draft"
    assert instruction["workflow"]["required_review_roles"]
    assert instruction["workflow"]["approval_blockers"]
    assert instruction["workflow"]["next_actions"]
    assert payload["evaluation"]["overall_score"] >= 0
    assert payload["evaluation"]["criteria"]
    assert "## Порядок выполнения" in payload["markdown"]


def test_generate_instruction_rejects_oversized_task() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate",
        json={"task": "проверить " * 260},
    )

    assert response.status_code == 422


def test_evaluate_instruction_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Подготовить рабочее место оператора перед запуском оборудования",
            "department": "Кузнечно-прессовый участок",
            "equipment": "Рабочее место оператора",
        },
    ).json()

    response = client.post(
        "/api/instructions/evaluate",
        json={"instruction": generated["instruction"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_score"] >= 0
    assert len(payload["criteria"]) == 10
    assert payload["risk_level"] in {"low", "medium", "high", "critical"}
    assert payload["expert_review_required"] is True
    assert payload["expert_review_notes"]


def test_export_pdf_endpoint_returns_watermarked_pdf(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Подготовить рабочее место оператора перед запуском оборудования",
            "department": "Кузнечно-прессовый участок",
            "equipment": "Рабочее место оператора",
        },
    ).json()

    response = client.post("/api/instructions/export-pdf", json=generated)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="instruction.pdf"' in response.headers["content-disposition"]
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_generate_with_context_returns_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-with-context",
        json={
            "task": "Подготовить рабочее место оператора перед запуском оборудования",
            "instruction_type": "workplace_preparation",
            "technical_context": "Проверить защитные ограждения и аварийную остановку.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"]
    assert any(source["source_type"] == "public" and source["url"] for source in payload["sources"])
    assert sum(1 for source in payload["sources"] if source["source_type"] == "public") > len(payload["sources"]) / 2
    assert len(payload["sources"]) <= 15
    assert all(0 <= source["influence_score"] <= 1 for source in payload["sources"])
    assert any(source["matched_terms"] for source in payload["sources"])
    assert any(source["authority"] for source in payload["sources"])
    assert any(source["document_type"] for source in payload["sources"])
    assert any(source["contribution_reason"] for source in payload["sources"])
    assert payload["evaluation"]["overall_score"] >= 0
    assert payload["evaluation"]["risk_level"] in {"low", "medium", "high", "critical"}
    combined_text = " ".join(
        [
            *payload["instruction"]["prerequisites"],
            *payload["instruction"]["control_points"],
            *payload["instruction"]["safety_requirements"],
        ]
    )
    assert "техническ" in combined_text.lower() or "документац" in combined_text.lower()


def test_generate_from_video_returns_step_frame_links(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "instruction_type": "equipment_startup",
            "technical_context": "На видео оператор проверяет ограждение и нажимает кнопку запуска.",
            "keyframes": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 2,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
            ],
            "frame_analyses": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 2,
                    "summary": "Оператор проверяет защитное ограждение станка перед запуском.",
                    "visible_equipment": ["станок", "защитное ограждение"],
                    "operator_actions": ["проверка ограждения"],
                    "analysis_mode": "fallback",
                }
            ],
            "video_segments": [
                {
                    "segment_index": 1,
                    "start_seconds": 2,
                    "end_seconds": 2,
                    "frame_indices": [10],
                    "summary": "Этап проверки защитного ограждения.",
                    "dominant_actions": ["проверка ограждения"],
                    "visible_equipment": ["станок", "защитное ограждение"],
                    "safety_findings": ["проверить опасную зону"],
                    "uncertainties": ["требуется проверка мастером"],
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["step_frame_links"]
    assert payload["step_frame_links"][0]["frame_index"] == 10
    assert payload["step_frame_links"][0]["image_url"] == "/generated/keyframes/test/a.jpg"
    assert "Видео: 00:02, кадр 10" in payload["markdown"]


def test_generate_from_video_rejects_cross_tenant_keyframe_reference(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "video-reference-bootstrap-token-32-plus",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": database_path,
        }
    )
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_a = create_organization("Reference A", database_path=database_path)
    organization_b = create_organization("Reference B", database_path=database_path)
    user_a = create_user(
        "reference-a@example.com",
        "Reference A",
        "strong-production-password-a",
        organization_id=organization_a,
        database_path=database_path,
    )
    token_a = create_session(user_a.user_id, database_path=database_path)
    video_id = "c" * 32
    payload = {
        "task": "Составить инструкцию по видео проверки защитного ограждения",
        "keyframes": [
            {
                "frame_index": 1,
                "timestamp_seconds": 1,
                "image_path": f"generated/keyframes/{organization_b}/{video_id}/frame_01.jpg",
                "image_url": f"/generated/keyframes/{organization_b}/{video_id}/frame_01.jpg",
            }
        ],
    }

    response = TestClient(app).post(
        "/api/instructions/generate-from-video",
        headers={"Authorization": f"Bearer {token_a}"},
        json=payload,
    )

    assert response.status_code == 400
    assert "current organization" in response.json()["error"]["message"]


def test_generate_from_video_accepts_existing_owned_keyframe(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "owned-reference-bootstrap-token-32-plus",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": database_path,
            "openai_enabled": False,
        }
    )
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)
    organization_id = create_organization("Owned Reference", database_path=database_path)
    user = create_user(
        "owned-reference@example.com",
        "Owned Reference",
        "strong-production-password-a",
        organization_id=organization_id,
        database_path=database_path,
    )
    token = create_session(user.user_id, database_path=database_path)
    video_id = "d" * 32
    relative_path = Path("generated") / "keyframes" / organization_id / video_id / "frame_01.jpg"
    frame_path = tmp_path / relative_path
    frame_path.parent.mkdir(parents=True)
    frame_path.write_bytes(b"frame")
    register_resource_ownership(
        organization_id,
        organization_id,
        "video",
        video_id,
        user.user_id,
        database_path=database_path,
    )
    monkeypatch.setattr("app.vision.keyframes.PROJECT_ROOT", tmp_path)

    response = TestClient(app).post(
        "/api/instructions/generate-from-video",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "task": "Составить инструкцию по видео проверки защитного ограждения",
            "keyframes": [
                {
                    "frame_index": 1,
                    "timestamp_seconds": 1,
                    "image_path": relative_path.as_posix(),
                    "image_url": f"/generated/keyframes/{organization_id}/{video_id}/frame_01.jpg",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text


def test_production_static_token_cannot_generate_instruction_without_user_session(
    tmp_path, monkeypatch
) -> None:
    static_token = "instruction-static-token-with-32-characters"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": static_token,
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": tmp_path / "auth.sqlite3",
        }
    )
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)

    response = TestClient(app).post(
        "/api/instructions/generate",
        headers={"Authorization": f"Bearer {static_token}"},
        json={"task": "Проверить ограждение"},
    )

    assert response.status_code == 401
    assert "Authenticated user session" in response.json()["error"]["message"]


def test_generate_from_video_rejects_excessive_keyframes() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "keyframes": [
                {
                    "frame_index": index,
                    "timestamp_seconds": index,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
                for index in range(33)
            ],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_compacts_long_video_context(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по длинному видео подготовки оборудования",
            "instruction_type": "equipment_startup",
            "technical_context": "Проверить ограждения, аварийную остановку и СИЗ. " * 900,
            "keyframes": [
                {
                    "frame_index": 1,
                    "timestamp_seconds": 1,
                    "image_path": "generated/keyframes/test/a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
            ],
            "frame_analyses": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["instruction"]["steps"]
    assert payload["instruction"]["local_verification_required"]
    assert payload["instruction"]["expert_review_questions"]
    assert "## Порядок выполнения" in payload["markdown"]


def test_generate_from_video_rejects_empty_keyframes() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "technical_context": "Видео обработано, но кадры не извлечены.",
            "keyframes": [],
            "frame_analyses": [],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_rejects_duplicate_keyframe_indices() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "keyframes": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                },
                {
                    "frame_index": 10,
                    "timestamp_seconds": 2,
                    "image_path": "b.jpg",
                    "image_url": "/generated/keyframes/test/b.jpg",
                },
            ],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_rejects_analysis_without_keyframe() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "frame_analyses": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1,
                    "summary": "Оператор проверяет станок.",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_rejects_mismatched_analysis_timestamp() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "keyframes": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
            ],
            "frame_analyses": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 5,
                    "summary": "Оператор проверяет станок.",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_rejects_segment_without_keyframe() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "keyframes": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
            ],
            "video_segments": [
                {
                    "segment_index": 1,
                    "start_seconds": 1,
                    "end_seconds": 1,
                    "frame_indices": [99],
                    "summary": "Этап с неизвестным кадром.",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_generate_from_video_rejects_duplicate_segment_indices() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/generate-from-video",
        json={
            "task": "Составить инструкцию по видео подготовки станка к запуску",
            "keyframes": [
                {
                    "frame_index": 10,
                    "timestamp_seconds": 1,
                    "image_path": "a.jpg",
                    "image_url": "/generated/keyframes/test/a.jpg",
                }
            ],
            "video_segments": [
                {
                    "segment_index": 1,
                    "start_seconds": 1,
                    "end_seconds": 1,
                    "frame_indices": [10],
                    "summary": "Первый этап.",
                },
                {
                    "segment_index": 1,
                    "start_seconds": 1,
                    "end_seconds": 1,
                    "frame_indices": [10],
                    "summary": "Дублирующий этап.",
                },
            ],
        },
    )

    assert response.status_code == 422


def test_rebuild_instruction_refreshes_markdown_and_evaluation(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Подготовить рабочее место оператора перед запуском оборудования"},
    ).json()
    generated["instruction"]["title"] = "Отредактированная инструкция запуска"
    generated["markdown"] = "stale markdown"

    response = client.post("/api/instructions/rebuild", json={"payload": generated})

    assert response.status_code == 200
    payload = response.json()
    assert payload["instruction"]["title"] == "Отредактированная инструкция запуска"
    assert "# Отредактированная инструкция запуска" in payload["markdown"]
    assert payload["evaluation"]["overall_score"] >= 0


def test_improve_instruction_returns_valid_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Проверить защитное ограждение станка перед запуском смены"},
    ).json()

    response = client.post(
        "/api/instructions/improve",
        json={
            "payload": generated,
            "source_request": {"task": "Проверить защитное ограждение станка перед запуском смены"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["instruction"]["steps"]
    assert payload["markdown"].startswith("# ")
    assert payload["evaluation"]["criteria"]


def test_improve_instruction_handles_short_title_without_source_request(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Проверить защитное ограждение станка перед запуском смены"},
    ).json()
    generated["instruction"]["title"] = "Пуск"

    response = client.post("/api/instructions/improve", json={"payload": generated})

    assert response.status_code == 200
    assert response.json()["instruction"]["steps"]


def test_instruction_response_rejects_unbounded_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": False,
                "openai_api_key": None,
                "openai_model": "test-model",
                "openai_timeout_seconds": 1,
            },
        )(),
    )
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Проверить защитное ограждение станка перед запуском смены"},
    ).json()
    generated["sources"] = [
        {
            "source_id": f"s-{index}",
            "title": "Source",
            "path": "source.md",
            "chunk_index": index,
            "score": 1,
            "excerpt": "Excerpt",
        }
        for index in range(31)
    ]

    response = client.post("/api/instructions/rebuild", json={"payload": generated})

    assert response.status_code == 422


def test_compact_video_context_handles_small_limits() -> None:
    compacted = _compact_video_context("A" * 1000, max_chars=120)

    assert compacted
    assert "Контекст видео" in compacted


def test_retrieve_endpoint_returns_sources() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/instructions/retrieve",
        json={
            "task": "Остановить оборудование и передать смену",
            "instruction_type": "equipment_shutdown",
        },
    )

    assert response.status_code == 200
    assert response.json()


def test_hsts_is_sent_only_in_production(tmp_path, monkeypatch) -> None:
    demo = TestClient(app).get("/health")

    assert "Strict-Transport-Security" not in demo.headers

    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "production-observability-token-at-least-32-chars",
            "allow_unauthenticated_access": False,
            "database_path": tmp_path / "hsts.sqlite3",
            "metrics_database_path": tmp_path / "hsts-metrics.sqlite3",
        }
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)

    production = TestClient(app, base_url="https://testserver").get("/health")

    assert production.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
