import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import get_session
from app.main import create_app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    settings = Settings(_env_file=None, database_url="sqlite://")
    with TestClient(create_app(settings, engine=engine)) as client:
        yield client
    engine.dispose()


def test_health_checks_database(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_database_failure_is_safe(client):
    class FailedSession:
        def execute(self, _query):
            raise OperationalError("secret signed URL", {}, Exception("private credentials"))

    client.app.dependency_overrides[get_session] = lambda: FailedSession()
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"error": {
        "code": "DATABASE_UNAVAILABLE", "message": "Database is unavailable", "details": None
    }}
    assert "secret" not in response.text


def test_missing_business_endpoint_returns_contract_error(client):
    response = client.get("/api/v1/evaluations/not-implemented")
    assert response.status_code == 404
    assert response.json() == {"error": {
        "code": "HTTP_404", "message": "Not Found", "details": None
    }}


def test_openapi_and_docs(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
    assert "ErrorEnvelope" in schema["components"]["schemas"]


def test_cors_allows_only_configured_origins(client):
    allowed = client.options("/api/v1/health", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"
    })
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.options("/api/v1/health", headers={
        "Origin": "https://unconfigured.invalid", "Access-Control-Request-Method": "GET"
    })
    assert "access-control-allow-origin" not in denied.headers


def test_unconfigured_prices_are_not_zero():
    settings = Settings(_env_file=None, llm_input_price_usd_per_1m="")
    assert settings.llm_input_price_usd_per_1m is None
