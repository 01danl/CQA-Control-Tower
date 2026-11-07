from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_migration_upgrade_downgrade_and_idempotency(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert "conversations" in inspect(engine).get_table_names()
    pk = inspect(engine).get_pk_constraint("conversations")
    assert pk["constrained_columns"] == ["group_id", "conversation_id"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM conversations")).scalar() == 0
    command.downgrade(config, "base")
    assert "conversations" not in inspect(engine).get_table_names()
    engine.dispose()
