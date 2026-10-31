from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QPQ_", extra="ignore", hide_input_in_errors=True)
    database_url: SecretStr
    environment: Literal["development", "test", "staging", "production"] = "production"
    dev_email_enabled: bool = False
    frontend_url: str = "http://localhost:3000"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    auth_enabled: bool = False
    uploads_enabled: bool = False
    storage_root: str = "/app/private-images"

    smtp_starttls: bool = False
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    email_sender: str = "noreply@qpqdata.test"
    session_seconds: int = Field(default=43200, ge=60, le=604800)
    session_idle_seconds: int = Field(default=1800, ge=30, le=86400)
    verification_ttl_seconds: int = Field(default=900, ge=30, le=3600)

    @model_validator(mode="after")
    def validate_development_email(self) -> "Settings":
        if self.uploads_enabled and self.environment not in {"development", "test"}:
            raise ValueError("Local image storage is restricted to development/test")
        if self.dev_email_enabled:
            if self.environment != "development":
                raise ValueError("Development email requires the development environment")
            url = urlsplit(self.frontend_url)
            if (
                url.scheme != "http"
                or url.hostname not in {"localhost", "127.0.0.1", "::1"}
                or url.username
                or url.password
                or url.query
                or url.fragment
                or url.path not in {"", "/"}
            ):
                raise ValueError("Development frontend URL must be a local HTTP origin")
            if (
                self.smtp_host not in {"mailpit", "localhost", "127.0.0.1", "::1"}
                or self.smtp_port != 1025
            ):
                raise ValueError(
                    "Development SMTP must use the local Mailpit listener on port 1025"
                )
        if self.auth_enabled:
            url = urlsplit(self.frontend_url)
            if (
                url.username
                or url.password
                or url.query
                or url.fragment
                or url.path not in {"", "/"}
                or not url.hostname
            ):
                raise ValueError("Frontend URL must be an origin")
            local = self.environment == "development" and url.hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }
            if url.scheme != "https" and not (local and url.scheme == "http"):
                raise ValueError("Authentication requires HTTPS outside loopback development")
            if self.environment != "development" and (
                not self.smtp_starttls
                or self.smtp_host in {"mailpit", "localhost", "127.0.0.1", "::1"}
                or self.email_sender.endswith(".test")
            ):
                raise ValueError(
                    "Production authentication requires configured TLS SMTP and sender"
                )
        return self
