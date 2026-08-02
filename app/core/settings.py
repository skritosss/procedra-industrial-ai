from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class Settings(BaseSettings):
    # Production is the default so that an unsafe deployment requires a
    # deliberate act. An image started with no environment at all previously
    # came up in demo mode: no API authentication, public registration, role
    # self-assignment, no video host allowlist and cookies without Secure.
    deployment_mode: Literal["demo", "production"] = "production"
    openai_api_key: str | None = None
    openai_enabled: bool = False
    openai_model: str = "gpt-4.1-mini"
    openai_vision_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    video_max_bytes: int = Field(default=250 * 1024 * 1024, ge=1 * 1024 * 1024, le=2 * 1024 * 1024 * 1024)
    video_max_duration_seconds: float = Field(default=1800.0, ge=10, le=7200)
    video_network_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    video_job_lease_seconds: int = Field(default=600, ge=30, le=7200)
    video_job_heartbeat_seconds: int = Field(default=15, ge=1, le=300)
    video_job_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    video_job_max_attempts: int = Field(default=3, ge=1, le=10)
    video_job_download_timeout_seconds: float = Field(default=900.0, ge=1, le=7200)
    video_job_extract_timeout_seconds: float = Field(default=900.0, ge=1, le=7200)
    video_job_analysis_timeout_seconds: float = Field(default=900.0, ge=1, le=7200)
    video_job_stage_poll_seconds: float = Field(default=0.25, ge=0.05, le=5)
    vision_max_keyframes: int = Field(default=8, ge=1, le=32)
    vision_max_image_bytes: int = Field(default=5 * 1024 * 1024, ge=100 * 1024, le=20 * 1024 * 1024)
    public_sources_enabled: bool = True
    public_sources_max_results: int = Field(default=15, ge=0, le=15)
    document_max_bytes: int = Field(default=15 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    database_path: Path = PROJECT_ROOT / "generated" / "app.sqlite3"
    metrics_database_path: Path = PROJECT_ROOT / "generated" / "metrics.sqlite3"
    # Separate file for the same reason the metrics store is separate: SQLite
    # allows one writer, and limiter bookkeeping must not queue behind business
    # data.
    rate_limit_database_path: Path = PROJECT_ROOT / "generated" / "rate_limits.sqlite3"
    metrics_bucket_seconds: int = Field(default=60, ge=10, le=3600)
    metrics_window_seconds: int = Field(default=300, ge=60, le=86_400)
    metrics_retention_seconds: int = Field(default=604_800, ge=3600, le=31_536_000)
    metrics_latency_threshold_ms: float = Field(default=2000.0, ge=10.0, le=300_000.0)
    metrics_availability_slo_percent: float = Field(default=99.0, ge=50.0, le=100.0)
    metrics_latency_slo_percent: float = Field(default=95.0, ge=50.0, le=100.0)
    metrics_alert_min_requests: int = Field(default=20, ge=1, le=1_000_000)
    metrics_public_enabled: bool = False
    api_access_token: str | None = None
    # Open access is an explicit choice, never a side effect of leaving
    # API_ACCESS_TOKEN unset. Production rejects it outright.
    allow_unauthenticated_access: bool = False
    auth_public_registration_enabled: bool = True
    auth_allow_role_self_assignment: bool = True
    auth_min_password_length: int = Field(default=8, ge=8, le=128)
    auth_session_ttl_seconds: int = Field(default=86_400, ge=300, le=31_536_000)
    auth_session_idle_timeout_seconds: int = Field(default=3_600, ge=300, le=31_536_000)
    auth_session_retention_seconds: int = Field(default=604_800, ge=3_600, le=31_536_000)
    auth_invitation_ttl_seconds: int = Field(default=259_200, ge=300, le=2_592_000)
    auth_max_active_sessions: int = Field(default=10, ge=1, le=100)
    # Per-account brute-force wall. The IP rate limit is per address, so it does
    # not stop a distributed attempt against one account.
    auth_max_failed_attempts: int = Field(default=10, ge=3, le=100)
    # Deliberately temporary. A permanent lock would let anyone who knows an
    # email address disable that person indefinitely.
    auth_lockout_seconds: int = Field(default=900, ge=30, le=86_400)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=60, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    # Coarse ceiling over the whole API, on every method. The narrow limits
    # below stay on top of it as the stricter rule.
    api_rate_limit_requests: int = Field(default=300, ge=10, le=100_000)
    api_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    auth_rate_limit_requests: int = Field(default=10, ge=1, le=1000)
    auth_rate_limit_window_seconds: int = Field(default=300, ge=1, le=3600)
    trust_proxy_headers: bool = False
    trusted_proxy_ips: Annotated[tuple[str, ...], NoDecode] = Field(default_factory=tuple)
    video_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = Field(default_factory=tuple)

    model_config = SettingsConfigDict(
        # Both files are read, left to right, so `.env.local` overrides `.env`.
        # Reading only `.env.local` meant that an administrator who copied
        # `.env.example` to `.env` — the conventional name, and the one the
        # README used to point at — was silently ignored, and the service came
        # up on defaults instead of the configuration that was just written.
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def empty_api_key_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("api_access_token", mode="before")
    @classmethod
    def empty_access_token_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("video_allowed_hosts", mode="before")
    @classmethod
    def parse_video_allowed_hosts(cls, value: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ()
        if isinstance(value, str):
            items = value.split(",")
        else:
            items = list(value)

        hosts: set[str] = set()
        for item in items:
            host = str(item).strip().lower().lstrip(".").rstrip(".")
            if not host:
                continue
            try:
                ip_address(host)
            except ValueError:
                if len(host) > 253 or any(not HOST_LABEL_PATTERN.fullmatch(label) for label in host.split(".")):
                    raise ValueError(f"Invalid host in VIDEO_ALLOWED_HOSTS: {item!r}") from None
            hosts.add(host)
        return tuple(sorted(hosts))

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, value: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ()
        items = value.split(",") if isinstance(value, str) else list(value)
        addresses = set()
        for item in items:
            candidate = str(item).strip()
            if not candidate:
                continue
            try:
                addresses.add(str(ip_address(candidate)))
            except ValueError:
                raise ValueError(f"Invalid IP address in TRUSTED_PROXY_IPS: {item!r}") from None
        return tuple(sorted(addresses))

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.metrics_database_path.resolve() == self.database_path.resolve():
            raise ValueError("METRICS_DATABASE_PATH must be separate from DATABASE_PATH")
        if self.rate_limit_database_path.resolve() == self.database_path.resolve():
            raise ValueError("RATE_LIMIT_DATABASE_PATH must be separate from DATABASE_PATH")
        if self.rate_limit_database_path.resolve() == self.metrics_database_path.resolve():
            raise ValueError("RATE_LIMIT_DATABASE_PATH must be separate from METRICS_DATABASE_PATH")
        if self.metrics_retention_seconds < self.metrics_window_seconds:
            raise ValueError("METRICS_RETENTION_SECONDS must be at least METRICS_WINDOW_SECONDS")
        if self.metrics_window_seconds < self.metrics_bucket_seconds:
            raise ValueError("METRICS_WINDOW_SECONDS must be at least METRICS_BUCKET_SECONDS")
        if self.auth_session_idle_timeout_seconds > self.auth_session_ttl_seconds:
            raise ValueError("AUTH_SESSION_IDLE_TIMEOUT_SECONDS must not exceed AUTH_SESSION_TTL_SECONDS")
        if self.video_job_heartbeat_seconds * 2 >= self.video_job_lease_seconds:
            raise ValueError("VIDEO_JOB_HEARTBEAT_SECONDS must be less than half VIDEO_JOB_LEASE_SECONDS")
        if self.deployment_mode != "production":
            return self
        unsafe_options = []
        if not self.api_access_token or len(self.api_access_token) < 32:
            unsafe_options.append("API_ACCESS_TOKEN must contain at least 32 characters")
        if self.allow_unauthenticated_access:
            unsafe_options.append("ALLOW_UNAUTHENTICATED_ACCESS must be false")
        if self.auth_public_registration_enabled:
            unsafe_options.append("AUTH_PUBLIC_REGISTRATION_ENABLED must be false")
        if self.auth_allow_role_self_assignment:
            unsafe_options.append("AUTH_ALLOW_ROLE_SELF_ASSIGNMENT must be false")
        if not self.rate_limit_enabled:
            unsafe_options.append("RATE_LIMIT_ENABLED must be true")
        if self.auth_min_password_length < 12:
            unsafe_options.append("AUTH_MIN_PASSWORD_LENGTH must be at least 12")
        if self.metrics_public_enabled:
            unsafe_options.append("METRICS_PUBLIC_ENABLED must be false")
        if self.trust_proxy_headers and not self.trusted_proxy_ips:
            unsafe_options.append("TRUSTED_PROXY_IPS must be configured when proxy headers are trusted")
        if not self.video_allowed_hosts:
            unsafe_options.append("VIDEO_ALLOWED_HOSTS must contain at least one host")
        if unsafe_options:
            raise ValueError("Unsafe production configuration: " + "; ".join(unsafe_options))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
