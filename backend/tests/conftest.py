import pytest
from sqlalchemy import create_engine, event

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
    )


@pytest.fixture
def engine(tmp_path):
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
