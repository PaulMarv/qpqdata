from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def test_live_and_openapi_do_not_require_database() -> None:
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/v1/health/live").json() == {"status": "ok", "service": "qpqdata-api"}
    assert client.get("/openapi.json").status_code == 200


def test_readiness_with_matching_schema() -> None:
    app = create_app()
    app.state.engine = MagicMock()
    connection = app.state.engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar.return_value = "0005"
    assert TestClient(app).get("/api/v1/health/ready").status_code == 200


def test_readiness_hides_database_errors() -> None:
    app = create_app()
    app.state.engine = MagicMock()
    app.state.engine.connect.side_effect = OperationalError("secret payload", {}, Exception())
    response = TestClient(app).get("/api/v1/health/ready")
    assert response.status_code == 503
    assert "secret" not in response.text


def test_unmigrated_database_is_not_ready() -> None:
    app = create_app()
    app.state.engine = MagicMock()
    connection = app.state.engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar.return_value = None
    assert TestClient(app).get("/api/v1/health/ready").status_code == 503


def test_lifespan_disposes_engine() -> None:
    from unittest.mock import patch

    with patch("app.main.make_engine") as factory:
        with TestClient(create_app(Settings(database_url="postgresql+psycopg://unused"))):
            pass
        factory.return_value.dispose.assert_called_once()


def test_cors_does_not_allow_unknown_origins() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/health/live", headers={"Origin": "https://unknown.example"}
    )
    assert "access-control-allow-origin" not in response.headers


def test_committed_openapi_matches_application() -> None:
    import json
    from pathlib import Path

    contract = Path(__file__).resolve().parents[2] / "frontend/openapi.json"
    assert json.loads(contract.read_text()) == create_app().openapi()
