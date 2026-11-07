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

from app.config import Settings
from app.db import get_session, make_engine, make_session_factory
from app.schemas import ErrorEnvelope, HealthResponse


def error_response(status: int, code: str, message: str, details=None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app(settings: Settings | None = None, *, engine=None) -> FastAPI:
    settings = settings or Settings()
    database_engine = engine if engine is not None else make_engine(settings)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if engine is None:
            database_engine.dispose()

    app = FastAPI(title="CQA Control Tower", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = make_session_factory(database_engine)
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

    return app


app = create_app()
