from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Conversation(Base):
    """Import storage boundary; no imported or seeded customer data at bootstrap."""

    __tablename__ = "conversations"

    group_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    language: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(40))
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Keep source order and timestamp strings; no lossy timestamp coercion.
    transcript: Mapped[list[dict]] = mapped_column(JSON)
