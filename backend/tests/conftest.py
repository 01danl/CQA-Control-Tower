from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text

from app.config import Settings
from app.db import Base, make_session_factory
from app.rubrics import seed_default


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        http_retries=1,
        retry_backoff_seconds=0,
        worker_poll_seconds=0.02,
        openai_api_key=None,
        llm_model=None,
        cqa_dataset_url=None,
        llm_input_price_usd_per_1m=None,
        llm_output_price_usd_per_1m=None,
    )


def pytest_addoption(parser):
    parser.addoption(
        "--postgres",
        action="store_true",
        help="Run service/API tests in disposable PostgreSQL schemas",
    )


@pytest.fixture
def engine(tmp_path, request):
    if request.config.getoption("--postgres"):
        schema = "cqa_test_" + uuid4().hex
        engine = create_engine(
            Settings().database_url.get_secret_value(),
            connect_args={"options": f"-csearch_path={schema}"},
        )
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
        with make_session_factory(engine)() as session:
            seed_default(session)
        try:
            yield engine
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            engine.dispose()
        return
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.sqlite'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        seed_default(session)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with make_session_factory(engine)() as session:
        yield session
