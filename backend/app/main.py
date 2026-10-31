from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.auth_api import router as auth_router
from app.config import Settings
from app.db import make_engine
from app.dev_email_api import router as dev_email_router
from app.project_api import router as project_router


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    service: Literal["qpqdata-api"] = "qpqdata-api"


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        app.state.settings = config
        app.state.engine = make_engine(config.database_url.get_secret_value())
        try:
            yield
        finally:
            await run_in_threadpool(app.state.engine.dispose)

    app = FastAPI(title="QPQData API", version="0.1.0", lifespan=lifespan)
    app.include_router(dev_email_router)
    app.include_router(auth_router)
    app.include_router(project_router)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        if "/auth/" in request.url.path or request.url.path.startswith("/api/v1/projects"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Cookie"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "Invalid request."})

    # Browser mutations use the same-origin Next.js transport, not credentialed CORS.
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
                if revision != "0004":
                    raise RuntimeError("schema unavailable")
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse(
                status_code=503, content=HealthResponse(status="unavailable").model_dump()
            )
        return HealthResponse(status="ok")

    return app


app = create_app()
