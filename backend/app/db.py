from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from starlette.requests import Request

from app.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings):
    url = settings.database_url.get_secret_value()
    options = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


def make_session_factory(engine):
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
