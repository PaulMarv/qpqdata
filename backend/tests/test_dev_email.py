from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.services.dev_email import (
    VerificationError,
    approved_domain,
    normalise_address,
    send_verification,
)
from app.services.dev_seed import require_development


def development(**overrides) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://unused",
        environment="development",
        dev_email_enabled=True,
        **overrides,
    )


@pytest.mark.parametrize(
    "address",
    ["student@university.test", "student+two@university.test", "other.person@university.test"],
)
def test_fixture_addresses(address: str) -> None:
    assert normalise_address(address.upper()) == address


@pytest.mark.parametrize(
    "address",
    [
        "student@gmail.com",
        "student@unknown.test",
        "student@sub.university.test",
        "student@university.test.attacker.example",
        "student@eviluniversity.test",
        "student@@university.test",
        "x\r\nBcc:x@university.test",
    ],
)
def test_other_domains_and_invalid_addresses_rejected(address: str) -> None:
    with pytest.raises(VerificationError):
        normalise_address(address)


@pytest.mark.parametrize("environment", ["staging", "production", "test"])
def test_dev_feature_cannot_enable_outside_development(environment: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://unused",
            environment=environment,
            dev_email_enabled=True,
        )
    settings = Settings(database_url="postgresql+psycopg://unused", environment=environment)
    with pytest.raises(ValueError):
        require_development(settings)
    with pytest.raises(ValueError):
        approved_domain(MagicMock(), settings)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://evil.localhost:3000",
        "http://localhost:3000/path",
        "http://localhost:3000?token=anything",
    ],
)
def test_external_or_non_origin_frontend_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        development(frontend_url=url)


def test_external_smtp_rejected() -> None:
    with pytest.raises(ValidationError):
        development(smtp_host="smtp.example.com")


def test_mail_uses_fragment_and_configured_local_frontend(monkeypatch, caplog) -> None:
    smtp = MagicMock()
    monkeypatch.setattr("app.integrations.email.smtplib.SMTP", smtp)
    secret = "synthetic-verification-secret"
    send_verification(
        development(frontend_url="http://127.0.0.1:3001"), "student@university.test", secret
    )
    smtp.assert_called_once_with("mailpit", 1025, timeout=5)
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "http://127.0.0.1:3001/dev-email/verify#token=" in body
    assert "?token=" not in body
    assert secret not in caplog.text


def test_disabled_endpoints_and_redacted_validation() -> None:
    client = TestClient(create_app())
    assert (
        client.post(
            "/api/v1/dev-email/register", json={"email": "student@university.test"}
        ).status_code
        == 404
    )
    secret = "do-not-echo-this-secret"
    response = client.post("/api/v1/dev-email/verify", json={"token": {"secret": secret}})
    assert response.status_code == 422
    assert secret not in response.text
