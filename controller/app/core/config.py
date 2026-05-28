"""Application configuration via Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables with sensible defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="THESIS_", extra="ignore")

    # Service identity
    service_name: str = "thesis-controller"
    service_version: str = "0.1.0"
    environment: str = "lab"  # "lab" | "production" | "test"

    # Database
    database_url: str = "sqlite+aiosqlite:///data/thesis.db"
    database_echo: bool = False

    # HTTP server
    host: str = "0.0.0.0"
    port: int = 8000

    # Security — Nginx forwarded headers
    trusted_proxy_header_verify: str = "x-client-verify"
    trusted_proxy_header_dn: str = "x-client-dn"

    # When True, allow requests without mTLS headers (dev/test only)
    allow_unauthenticated: bool = False

    # Certificate revocation — controller fetches step-ca's CRL and rejects
    # requests bearing a revoked client-cert serial (Zero Trust: re-checked per
    # request, not just at the TLS handshake).
    crl_url: str = "https://ca.thesis.local:9000/crl"
    ca_trust_file: str = "/etc/thesis-certs/ca-trust.crt"
    crl_refresh_seconds: int = 60


settings = Settings()
