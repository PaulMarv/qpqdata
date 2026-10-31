from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/api/v1/health/live", response_model=HealthResponse, operation_id="getLiveness")
def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/api/v1/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    operation_id="getReadiness",
)
def ready(request: Request) -> HealthResponse | JSONResponse:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision != "0005":
                raise RuntimeError("schema unavailable")
    except (SQLAlchemyError, RuntimeError):
        return JSONResponse(
            status_code=503, content=HealthResponse(status="unavailable").model_dump()
        )
    return HealthResponse(status="ok")
