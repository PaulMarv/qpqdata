import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.services.auth import normalise_email


def test_real_email_parser_and_idna() -> None:
    assert normalise_email("Student@UNIVERSITY.test") == "student@university.test"
    assert normalise_email("worker@bücher.de") == "worker@xn--bcher-kva.de"


@pytest.mark.parametrize(
    "address", ["x@@example.org", "x\r\nBcc: a@example.org", "x@", "x@unknown"]
)
def test_invalid_email(address) -> None:
    from app.services.auth import AuthError

    with pytest.raises(AuthError):
        normalise_email(address)


def test_production_settings_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://unused", auth_enabled=True)
    config = Settings(
        database_url="postgresql+psycopg://unused",
        auth_enabled=True,
        frontend_url="https://qpq.example.org",
        smtp_starttls=True,
        smtp_host="smtp.example.org",
        email_sender="noreply@qpq.example.org",
    )
    assert config.environment == "production"


def test_auth_disabled_by_default() -> None:
    client = TestClient(create_app())
    assert client.get("/api/v1/auth/me").status_code == 404


def test_legacy_activation_error_is_sanitised(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from app.services.auth import AuthError

    def unavailable(*args):
        raise AuthError("Internal grant error", 503)

    monkeypatch.setattr("app.api.routes.dev_email.verify", unavailable)
    app = create_app()
    app.state.settings = Settings(
        database_url="postgresql+psycopg://unused",
        environment="development",
        dev_email_enabled=True,
        auth_enabled=True,
    )
    app.state.engine = MagicMock()
    response = TestClient(app).post("/api/v1/dev-email/verify", json={"token": "s" * 43})
    assert response.status_code == 503
    assert "Internal grant error" not in response.text
