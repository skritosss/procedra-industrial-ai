from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_video_worker_cli_bootstraps_project_imports() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_video_job_worker.py", "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "durable Procedra video-job worker" in completed.stdout


def test_dockerfile_uses_non_root_runtime_and_healthcheck() -> None:
    dockerfile = _read("Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "OPENAI_ENABLED=false" in dockerfile
    assert "PUBLIC_SOURCES_ENABLED=true" in dockerfile
    assert "PUBLIC_SOURCES_MAX_RESULTS=15" in dockerfile
    assert "DATABASE_PATH=/app/generated/app.sqlite3" in dockerfile
    assert "METRICS_DATABASE_PATH=/app/generated/metrics.sqlite3" in dockerfile
    assert "VIDEO_MAX_DURATION_SECONDS=1800" in dockerfile
    assert "fonts-dejavu-core" in dockerfile
    assert "libgomp1" in dockerfile
    assert "mkdir -p /app/generated/keyframes /app/uploads/videos" in dockerfile
    assert "COPY scripts/cleanup_artifacts.py ./scripts/cleanup_artifacts.py" in dockerfile
    assert "COPY scripts/manage_database.py ./scripts/manage_database.py" in dockerfile
    assert "COPY scripts/reconcile_document_ownership.py ./scripts/reconcile_document_ownership.py" in dockerfile
    assert "COPY scripts/run_video_job_worker.py ./scripts/run_video_job_worker.py" in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "urllib.request.urlopen('http://127.0.0.1:8000/health'" in dockerfile


def test_dockerignore_excludes_secrets_and_runtime_artifacts() -> None:
    dockerignore = _read(".dockerignore").splitlines()

    assert ".env" in dockerignore
    assert ".env.*" in dockerignore
    assert "!.env.example" in dockerignore
    assert ".venv" in dockerignore
    assert "generated/" in dockerignore
    assert "uploads/" in dockerignore


def test_env_example_is_safe_for_deterministic_local_demo() -> None:
    env_example = _read(".env.example")

    assert "OPENAI_ENABLED=false" in env_example
    assert "OPENAI_API_KEY=" in env_example
    assert "Set OPENAI_ENABLED=true" in env_example
    assert "VIDEO_MAX_BYTES=262144000" in env_example
    assert "VIDEO_MAX_DURATION_SECONDS=1800" in env_example
    assert "VIDEO_NETWORK_TIMEOUT_SECONDS=15" in env_example
    assert "VISION_MAX_KEYFRAMES=8" in env_example
    assert "VISION_MAX_IMAGE_BYTES=5242880" in env_example
    assert "DATABASE_PATH=generated/app.sqlite3" in env_example
    assert "METRICS_DATABASE_PATH=generated/metrics.sqlite3" in env_example
    assert "METRICS_AVAILABILITY_SLO_PERCENT=99" in env_example
    assert "METRICS_LATENCY_SLO_PERCENT=95" in env_example
    assert "METRICS_PUBLIC_ENABLED=false" in env_example
    assert "AUTH_SESSION_IDLE_TIMEOUT_SECONDS=3600" in env_example
    assert "AUTH_SESSION_RETENTION_SECONDS=604800" in env_example
    assert "PUBLIC_SOURCES_ENABLED=true" in env_example
    assert "PUBLIC_SOURCES_MAX_RESULTS=15" in env_example
    assert "APP_PORT=8000" in env_example
    assert "APP_BIND_HOST=127.0.0.1" in env_example


def test_requirements_include_runtime_typecheck_and_testclient_dependencies() -> None:
    requirements = _read("requirements.txt")

    assert "httpx2==2.3.0" in requirements
    assert "reportlab==4.5.1" in requirements
    assert "mypy==1.20.2" in requirements
    assert all(
        "==" in line
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def test_compose_defaults_to_deterministic_demo_mode_and_persistent_volumes() -> None:
    compose = _read("docker-compose.yml")

    assert 'OPENAI_ENABLED: "${OPENAI_ENABLED:-false}"' in compose
    assert 'VIDEO_NETWORK_TIMEOUT_SECONDS: "${VIDEO_NETWORK_TIMEOUT_SECONDS:-15}"' in compose
    assert 'VIDEO_MAX_DURATION_SECONDS: "${VIDEO_MAX_DURATION_SECONDS:-1800}"' in compose
    assert 'PUBLIC_SOURCES_ENABLED: "${PUBLIC_SOURCES_ENABLED:-true}"' in compose
    assert 'PUBLIC_SOURCES_MAX_RESULTS: "${PUBLIC_SOURCES_MAX_RESULTS:-15}"' in compose
    assert 'DATABASE_PATH: "${DATABASE_PATH:-/app/generated/app.sqlite3}"' in compose
    assert 'METRICS_DATABASE_PATH: "${METRICS_DATABASE_PATH:-/app/generated/metrics.sqlite3}"' in compose
    assert 'METRICS_PUBLIC_ENABLED: "${METRICS_PUBLIC_ENABLED:-false}"' in compose
    assert 'AUTH_SESSION_IDLE_TIMEOUT_SECONDS: "${AUTH_SESSION_IDLE_TIMEOUT_SECONDS:-3600}"' in compose
    assert 'AUTH_SESSION_RETENTION_SECONDS: "${AUTH_SESSION_RETENTION_SECONDS:-604800}"' in compose
    assert "video-job-worker:" in compose
    assert 'command: ["python", "scripts/run_video_job_worker.py"]' in compose
    assert 'VIDEO_JOB_LEASE_SECONDS: "${VIDEO_JOB_LEASE_SECONDS:-600}"' in compose
    assert 'VIDEO_JOB_DOWNLOAD_TIMEOUT_SECONDS: "${VIDEO_JOB_DOWNLOAD_TIMEOUT_SECONDS:-900}"' in compose
    assert 'VIDEO_JOB_EXTRACT_TIMEOUT_SECONDS: "${VIDEO_JOB_EXTRACT_TIMEOUT_SECONDS:-900}"' in compose
    assert 'VIDEO_JOB_ANALYSIS_TIMEOUT_SECONDS: "${VIDEO_JOB_ANALYSIS_TIMEOUT_SECONDS:-900}"' in compose
    assert 'VIDEO_JOB_STAGE_POLL_SECONDS: "${VIDEO_JOB_STAGE_POLL_SECONDS:-0.25}"' in compose
    worker_section = compose.split("  video-job-worker:", maxsplit=1)[1]
    assert "healthcheck:\n      disable: true" in worker_section
    assert '"${APP_BIND_HOST:-127.0.0.1}:${APP_PORT:-8000}:8000"' in compose
    assert "init: true" in compose
    assert "- generated-data:/app/generated" in compose
    assert "- upload-data:/app/uploads" in compose
    assert "healthcheck:" in compose
    assert "urllib.request.urlopen('http://127.0.0.1:8000/health'" in compose
    assert "restart: unless-stopped" in compose


def test_deployment_doc_includes_repeatable_smoke_checklist() -> None:
    deployment = _read("docs/deployment.md")

    assert "Production Smoke Checklist" in deployment
    assert "python -m compileall -q app tests scripts" in deployment
    assert "python -m pytest -q" in deployment
    assert "docker compose config" in deployment
    assert "curl http://127.0.0.1:8000/health" in deployment
    assert "/api/instructions/generate" in deployment
    assert "PUBLIC_SOURCES_MAX_RESULTS" in deployment
    assert "make docker-config" in deployment
    assert "manage_database.py backup" in deployment
    assert "manage_database.py restore" in deployment
    assert "pre-restore safety backup" in deployment


def test_partner_demo_doc_includes_live_demo_contract() -> None:
    partner_demo = _read("docs/partner_demo.md")

    assert "make smoke" in partner_demo
    assert "make safety-eval" in partner_demo
    assert "make demo-eval" in partner_demo
    assert "source count set to 15" in partner_demo
    assert "PDF export" in partner_demo
    assert "Honest Boundaries" in partner_demo
    assert "critical false-confidence cases are locally covered by S1" in partner_demo
    assert "This is regression" in partner_demo
    assert "must not be presented as proof of correctness" in partner_demo
    assert "echoed from untrusted context" in partner_demo


def test_ci_runs_compile_tests_docker_build_and_compose_validation() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "concurrency:" in workflow
    assert "python -m compileall -q app tests scripts" in workflow
    assert "python -m pip check" in workflow
    assert "python -m pip_audit -r requirements.txt" in workflow
    assert "python -m mypy app scripts" in workflow
    assert "python -m pytest -q" in workflow
    assert "docker build -t industrial-instruction-ai:ci ." in workflow
    assert "docker run -d --name procedra-ci" in workflow
    assert 'test "$(docker exec procedra-ci id -u)" != "0"' in workflow
    assert "docker restart procedra-ci" in workflow
    assert "curl -fsS http://127.0.0.1:18000/ready" in workflow
    assert "docker compose config" in workflow
    assert "libgomp1" in workflow


def test_makefile_exposes_repeatable_project_commands() -> None:
    makefile = _read("Makefile")

    assert "PYTHON ?= python3.12" in makefile
    assert "install:" in makefile
    assert "$(PYTHON) -m venv $(VENV)" in makefile
    assert ".env:" in makefile
    assert "cp .env.example .env" in makefile
    assert "env: .env" in makefile
    assert "$(APP_PYTHON) -m pip install -r requirements.txt" in makefile
    assert "run:" in makefile
    assert "test:" in makefile
    assert "compile:" in makefile
    assert "typecheck:" in makefile
    assert "$(APP_PYTHON) -m mypy app scripts" in makefile
    assert "pip-check:" in makefile
    assert "demo-eval:" in makefile
    assert "$(APP_PYTHON) scripts/run_demo_eval.py" in makefile
    # Local targets that boot the app must state the demo mode; the default is production.
    assert "DEMO_ENV ?= DEPLOYMENT_MODE=demo ALLOW_UNAUTHENTICATED_ACCESS=true" in makefile
    assert "CLEANUP_MAX_AGE_HOURS ?= 24" in makefile
    assert "cleanup-plan:" in makefile
    assert (
        "scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS) "
        "--reconcile-video-ownership" in makefile
    )
    assert "cleanup-delete:" in makefile
    assert (
        "scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS) "
        "--reconcile-video-ownership --delete" in makefile
    )
    assert "scripts/reconcile_document_ownership.py --database \"$(DATABASE)\"" in makefile
    assert "scripts/reconcile_document_ownership.py --database \"$(DATABASE)\" --apply" in makefile
    assert "smoke:" in makefile
    assert "static-smoke:" in makefile
    assert "public-scope-audit:" in makefile
    assert "scripts/public_scope_audit.py --sample-limit 0" in makefile
    assert "safety-eval:" in makefile
    assert "scripts/run_safety_eval.py" in makefile
    assert "api-smoke:" in makefile
    assert "health:" in makefile
    assert "docker-build:" in makefile
    assert "docker-config:" in makefile
    assert "docker compose config" in makefile
    assert "curl -fsS http://$(HOST):$(PORT)/health" in makefile
    assert "ready:" in makefile
    assert "curl -fsS http://$(HOST):$(PORT)/ready" in makefile
    assert "ready-details:" in makefile
    assert "metrics:" in makefile
    assert "API_ACCESS_TOKEN is required for metrics" in makefile
    assert "TestClient(app)" in makefile


def test_settings_default_to_safe_demo_mode_and_strip_blank_api_key() -> None:
    settings = Settings(_env_file=None, openai_api_key="   ")

    assert settings.openai_enabled is False
    assert settings.openai_api_key is None
    assert settings.database_path.name == "app.sqlite3"
    assert settings.metrics_database_path.name == "metrics.sqlite3"
    assert settings.public_sources_enabled is True
    assert settings.public_sources_max_results == 15


def test_settings_require_separate_metrics_storage_and_valid_retention() -> None:
    with pytest.raises(ValidationError, match="must be separate"):
        Settings(
            _env_file=None,
            database_path="shared.sqlite3",
            metrics_database_path="shared.sqlite3",
        )
    with pytest.raises(ValidationError, match="must be at least"):
        Settings(
            _env_file=None,
            metrics_window_seconds=7_200,
            metrics_retention_seconds=3_600,
        )

    with pytest.raises(ValidationError, match="IDLE_TIMEOUT"):
        Settings(
            _env_file=None,
            auth_session_ttl_seconds=600,
            auth_session_idle_timeout_seconds=601,
        )


@pytest.mark.parametrize("raw_value", ["", "   ", " , , "])
def test_settings_accept_empty_video_allowed_hosts(monkeypatch: pytest.MonkeyPatch, raw_value: str) -> None:
    monkeypatch.setenv("VIDEO_ALLOWED_HOSTS", raw_value)

    assert Settings(_env_file=None).video_allowed_hosts == ()


def test_settings_parse_video_allowed_hosts_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "VIDEO_ALLOWED_HOSTS",
        " YouTube.com, youtu.be, youtube.com, .RUTUBE.RU. ",
    )

    assert Settings(_env_file=None).video_allowed_hosts == ("rutube.ru", "youtu.be", "youtube.com")


def test_settings_reject_unsafe_production_auth_configuration() -> None:
    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings(_env_file=None, deployment_mode="production")


def test_settings_reject_short_production_bootstrap_token() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            deployment_mode="production",
            allow_unauthenticated_access=False,
            api_access_token="too-short",
            auth_public_registration_enabled=False,
            auth_allow_role_self_assignment=False,
            auth_min_password_length=12,
        )


def test_settings_accept_hardened_production_auth_configuration() -> None:
    settings = Settings(
        _env_file=None,
        deployment_mode="production",
        allow_unauthenticated_access=False,
        api_access_token="production-bootstrap-token-at-least-32-chars",
        auth_public_registration_enabled=False,
        auth_allow_role_self_assignment=False,
        auth_min_password_length=12,
        video_allowed_hosts="youtube.com,youtu.be",
    )

    assert settings.deployment_mode == "production"
    assert settings.auth_public_registration_enabled is False
    assert settings.auth_allow_role_self_assignment is False
    assert settings.video_allowed_hosts == ("youtu.be", "youtube.com")


def test_settings_reject_public_metrics_in_production() -> None:
    with pytest.raises(ValidationError, match="METRICS_PUBLIC_ENABLED must be false"):
        Settings(
            _env_file=None,
            deployment_mode="production",
            allow_unauthenticated_access=False,
            api_access_token="production-bootstrap-token-at-least-32-chars",
            auth_public_registration_enabled=False,
            auth_allow_role_self_assignment=False,
            auth_min_password_length=12,
            metrics_public_enabled=True,
            video_allowed_hosts="youtube.com",
        )


def test_settings_reject_production_without_video_host_allowlist() -> None:
    with pytest.raises(ValidationError, match="VIDEO_ALLOWED_HOSTS"):
        Settings(
            _env_file=None,
            deployment_mode="production",
            allow_unauthenticated_access=False,
            api_access_token="production-bootstrap-token-at-least-32-chars",
            auth_public_registration_enabled=False,
            auth_allow_role_self_assignment=False,
            auth_min_password_length=12,
        )


def test_settings_reject_unsafe_trusted_proxy_configuration() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_IPS"):
        Settings(
            _env_file=None,
            deployment_mode="production",
            allow_unauthenticated_access=False,
            api_access_token="production-bootstrap-token-at-least-32-chars",
            auth_public_registration_enabled=False,
            auth_allow_role_self_assignment=False,
            auth_min_password_length=12,
            trust_proxy_headers=True,
        )


def test_settings_parse_trusted_proxy_ips() -> None:
    settings = Settings(
        _env_file=None,
        trusted_proxy_ips="127.0.0.1, ::1,127.0.0.1",
    )

    assert settings.trusted_proxy_ips == ("127.0.0.1", "::1")


@pytest.mark.parametrize(
    "raw_value",
    ["https://youtube.com", "youtube.com/watch", "youtube.com:443", "*.youtube.com", "bad host"],
)
def test_settings_reject_malformed_video_allowed_hosts(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
) -> None:
    monkeypatch.setenv("VIDEO_ALLOWED_HOSTS", raw_value)

    with pytest.raises(ValidationError, match="Invalid host in VIDEO_ALLOWED_HOSTS"):
        Settings(_env_file=None)


def test_settings_reject_unsafe_runtime_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, video_max_bytes=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, video_network_timeout_seconds=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, video_max_duration_seconds=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, vision_max_keyframes=100)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, public_sources_max_results=16)


def test_settings_reject_invalid_timeout_and_image_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, openai_timeout_seconds=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, vision_max_image_bytes=1)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, video_max_bytes=3 * 1024 * 1024 * 1024)


def test_dockerfile_does_not_ship_the_docs_directory() -> None:
    dockerfile = _read("Dockerfile")

    # docs/ holds internal commercial and research drafts and is never read at
    # runtime, so a customer-delivered image must not contain it.
    assert "COPY docs" not in dockerfile


def test_dockerignore_excludes_internal_documents() -> None:
    dockerignore = _read(".dockerignore").splitlines()

    assert "docs/research/" in dockerignore
    assert "_internal/" in dockerignore
    assert "PRODUCT_ROADMAP.md" in dockerignore
    assert "docs/Предметная_часть_пилотного_хоздоговора_Procedra.md" in dockerignore


def test_settings_reject_unauthenticated_access_in_production() -> None:
    with pytest.raises(ValidationError, match="ALLOW_UNAUTHENTICATED_ACCESS must be false"):
        Settings(
            _env_file=None,
            deployment_mode="production",
            allow_unauthenticated_access=True,
            api_access_token="production-bootstrap-token-at-least-32-chars",
            auth_public_registration_enabled=False,
            auth_allow_role_self_assignment=False,
            auth_min_password_length=12,
            video_allowed_hosts="youtube.com",
        )


def test_settings_default_to_closed_access() -> None:
    settings = Settings(_env_file=None, deployment_mode="demo", allow_unauthenticated_access=False)

    # An unset API token must not authorise anyone by itself.
    assert settings.allow_unauthenticated_access is False
    assert settings.api_access_token is None


STAND_ENV_TEMPLATE = PROJECT_ROOT / "deploy" / "stand.env.example"


def _template_settings(path: Path, **overrides: object) -> Settings:
    """Build settings from a template file.

    The values are passed as arguments rather than through `_env_file` because
    the test session exports a demo environment, and environment variables win
    over an env file. Arguments win over both, so this reads the template and
    nothing else.
    """
    values: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip().lower()] = value.strip()
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_stand_template_refuses_to_start_until_a_token_is_generated() -> None:
    # The one field the template deliberately leaves empty. A stand that boots
    # with a placeholder secret is worse than one that refuses to boot.
    with pytest.raises(ValidationError, match="API_ACCESS_TOKEN"):
        _template_settings(STAND_ENV_TEMPLATE)


def test_stand_template_is_accepted_once_the_token_is_supplied() -> None:
    settings = _template_settings(
        STAND_ENV_TEMPLATE,
        api_access_token="stand-bootstrap-token-at-least-32-characters",
    )

    assert settings.deployment_mode == "production"
    assert settings.allow_unauthenticated_access is False
    assert settings.auth_public_registration_enabled is False
    assert settings.auth_allow_role_self_assignment is False
    assert settings.metrics_public_enabled is False
    assert settings.rate_limit_enabled is True
    # Switched off rather than allowlisted: the stand has no reason to reach out
    # for content, and an empty allowlist would mean "any public host".
    assert settings.video_url_ingest_enabled is False
    assert settings.video_allowed_hosts == ()
    # Compose publishes the port on this address; loopback keeps the container
    # behind the TLS proxy instead of on the host's public interface.
    assert "APP_BIND_HOST=127.0.0.1" in STAND_ENV_TEMPLATE.read_text(encoding="utf-8")


def test_stand_template_is_stricter_than_the_local_template() -> None:
    local = _template_settings(PROJECT_ROOT / ".env.example")
    stand = _template_settings(
        STAND_ENV_TEMPLATE,
        api_access_token="stand-bootstrap-token-at-least-32-characters",
    )

    assert stand.auth_min_password_length > local.auth_min_password_length
    assert stand.auth_session_idle_timeout_seconds < local.auth_session_idle_timeout_seconds
    assert stand.auth_max_failed_attempts < local.auth_max_failed_attempts
    assert stand.rate_limit_requests < local.rate_limit_requests
    assert stand.auth_rate_limit_requests < local.auth_rate_limit_requests


def test_a_missing_env_file_is_named_in_the_production_refusal(monkeypatch) -> None:
    """The hardening list is correct and useless to someone who just cloned the
    repository: their mistake is a missing file, not five unset switches."""
    import app.core.settings as settings_module

    monkeypatch.setattr(settings_module, "PROJECT_ROOT", PROJECT_ROOT / "no-such-directory")

    with pytest.raises(ValidationError, match="cp .env.example .env"):
        Settings(_env_file=None, deployment_mode="production")


def test_an_operator_with_an_env_file_is_not_told_to_copy_a_template(monkeypatch, tmp_path) -> None:
    """A deliberate production deployment must not be advised to overwrite its
    configuration with the demo template."""
    import app.core.settings as settings_module

    (tmp_path / ".env").write_text("DEPLOYMENT_MODE=production\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)

    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None, deployment_mode="production")
    assert "cp .env.example .env" not in str(raised.value)


def test_control_characters_do_not_reach_the_document() -> None:
    """They arrive only through the API, never the form, and travel from the
    request into the instruction, the Markdown and the PDF. Nothing inside this
    service breaks on them; an XML-based document system downstream does."""
    from app.generation.pipeline import generate_instruction
    from app.generation.pdf import render_instruction_pdf
    from app.schemas.instruction import InstructionRequest

    response = generate_instruction(
        InstructionRequest(
            task="Подготовка\x00\x07 рабочего места оператора",
            industry_profile="manufacturing",
            instruction_type="general",
        )
    )

    assert "\x00" not in response.instruction.title
    assert "\x00" not in response.markdown

    # The raw bytes always contain NUL — fonts and cross-reference tables are
    # binary. What matters is the text a reader and an exporter get out.
    import io

    from pypdf import PdfReader

    pages = PdfReader(io.BytesIO(render_instruction_pdf(response))).pages
    assert "\x00" not in "\n".join(page.extract_text() or "" for page in pages)


def test_line_breaks_and_tabs_survive() -> None:
    """A technical context is pasted from a document; its line breaks carry
    meaning and stripping them would lose the structure the author typed."""
    from app.schemas.instruction import InstructionRequest

    request = InstructionRequest(
        task="Подготовка рабочего места оператора",
        technical_context="Первая строка\nВторая строка\tс отступом",
    )

    assert request.technical_context == "Первая строка\nВторая строка\tс отступом"
