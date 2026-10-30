from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.db import make_engine


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    service: Literal["qpqdata-api"] = "qpqdata-api"


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        app.state.engine = make_engine(config.database_url.get_secret_value())
        try:
            yield
        finally:
            await run_in_threadpool(app.state.engine.dispose)

    app = FastAPI(title="QPQData API", version="0.1.0", lifespan=lifespan)
    # Explicit local origins; credentials remain disabled until authentication is reviewed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET"],
        allow_headers=["Accept"],
        allow_credentials=False,
    )

    @app.get("/api/v1/health/live", response_model=HealthResponse, operation_id="getLiveness")
    def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/api/v1/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse}},
        operation_id="getReadiness",
    )
    def ready(request: Request) -> HealthResponse | JSONResponse:
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
                if revision != "0001":
                    raise RuntimeError("schema unavailable")
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse(
                status_code=503, content=HealthResponse(status="unavailable").model_dump()
            )
        return HealthResponse(status="ok")

    return app


app = create_app()
