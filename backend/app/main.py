import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.routes.auth import router as auth_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.dev_email import router as dev_email_router
from app.api.routes.health import router as health_router
from app.api.routes.moderation import router as moderation_router
from app.api.routes.projects import router as project_router
from app.api.routes.submissions import router as submission_router
from app.core.config import Settings
from app.db.session import make_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        app.state.settings = config
        app.state.download_gate = asyncio.Semaphore(4)
        app.state.upload_gate = asyncio.Semaphore(4)
        app.state.engine = make_engine(config.database_url.get_secret_value())
        try:
            yield
        finally:
            await run_in_threadpool(app.state.engine.dispose)

    app = FastAPI(title="QPQData API", version="0.1.0", lifespan=lifespan)
    app.include_router(dev_email_router)
    app.include_router(auth_router)
    app.include_router(project_router)
    app.include_router(submission_router)
    app.include_router(moderation_router)
    app.include_router(datasets_router)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith(
            ("/api/v1/submissions", "/api/v1/projects", "/api/v1/moderation", "/api/v1/datasets")
        ):
            payload = bytearray()
            try:
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        if len(payload) + len(chunk) > 65536:
                            return JSONResponse(
                                status_code=413, content={"detail": "Request too large."}
                            )
                        payload.extend(chunk)
                request._body = bytes(payload)
            except TimeoutError:
                return JSONResponse(status_code=408, content={"detail": "Request timed out."})
        response = await call_next(request)
        if "/auth/" in request.url.path or request.url.path.startswith(
            (
                "/api/v1/projects",
                "/api/v1/submissions",
                "/api/v1/moderation",
                "/api/v1/wallet",
                "/api/v1/datasets",
            )
        ):
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

    app.include_router(health_router)

    return app


app = create_app()
