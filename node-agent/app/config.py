"""Env-driven configuration. Loaded once at startup; no runtime mutation."""
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="THESIS_",
        env_file=None,  # systemd EnvironmentFile handles loading
        case_sensitive=False,
    )

    # Identity
    node_id: str = Field(default="pi-01")
    node_common_name: str = Field(default="pi-01.thesis.local")
    node_role: str = Field(default="valid")

    # Controller
    controller_url: str = Field(default="https://controller.thesis.local")
    controller_ca: Path = Field(default=Path("/etc/thesis-lab/certs/ca-root.crt"))

    # mTLS client identity
    client_cert: Path = Field(default=Path("/etc/thesis-lab/certs/pi-01.crt"))
    client_key: Path = Field(default=Path("/etc/thesis-lab/certs/pi-01.key"))

    # Heartbeat
    heartbeat_interval: int = Field(default=30, ge=5)
    heartbeat_jitter: int = Field(default=5, ge=0)

    # Metrics listener
    metrics_port: int = Field(default=9100, ge=1, le=65535)
    metrics_bind: str = Field(default="0.0.0.0")
    # Comma-separated. Parsed by validator into a frozen set.
    allowed_scraper_cns: str = Field(default="prometheus.thesis.local")

    # Logging
    log_level: str = Field(default="INFO")

    @field_validator("controller_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    def allowed_cns_set(self) -> frozenset[str]:
        """Parse comma-separated env value to a set for O(1) membership checks."""
        return frozenset(s.strip() for s in self.allowed_scraper_cns.split(",") if s.strip())


settings = Settings()
