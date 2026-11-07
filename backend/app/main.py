from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.api import router
from app.batch import JobRunner
from app.config import Settings
from app.dataset_client import DatasetClient
from app.db import get_session, make_engine, make_session_factory
from app.errors import ServiceError
from app.providers import LLMProvider, OpenAIProvider
from app.rubrics import seed_default
from app.schemas import ErrorEnvelope, HealthResponse


def error_response(status: int, code: str, message: str, details=None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app(
    settings: Settings | None = None,
    *,
    engine=None,
    provider: LLMProvider | None = None,
    dataset_client: DatasetClient | None = None,
    start_workers: bool = True,
) -> FastAPI:
    settings = settings or Settings()
    database_engine = engine if engine is not None else make_engine(settings)
    factory = make_session_factory(database_engine)
    runner = JobRunner(factory, provider or OpenAIProvider(settings), settings)

    @asynccontextmanager
    async def lifespan(_app):
        with factory() as session:
            seed_default(session)
        if start_workers:
            runner.start()
        try:
            yield
        finally:
            if start_workers:
                runner.stop()
            if engine is None:
                database_engine.dispose()

    app = FastAPI(title="CQA Control Tower", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = factory
    app.state.settings = settings
    app.state.dataset_client = dataset_client or DatasetClient(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return error_response(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        # Do not echo input values, which can contain customer text or credentials.
        details = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return error_response(422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def unexpected_error(_request, _exc):
        return error_response(500, "INTERNAL_ERROR", "Unexpected server error")

    @app.exception_handler(ServiceError)
    async def service_error(_request, exc: ServiceError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, _exc):
        return error_response(503, "DATABASE_ERROR", "Database operation failed")

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        responses={503: {"model": ErrorEnvelope}},
        tags=["health"],
    )
    def health(session: Annotated[Session, Depends(get_session)]):
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return error_response(503, "DATABASE_UNAVAILABLE", "Database is unavailable")
        return HealthResponse()

    app.include_router(router)
    return app


app = create_app()
