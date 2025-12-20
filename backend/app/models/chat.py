from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship

from .base import Base


def _uuid_hex() -> str:
    return uuid.uuid4().hex


class ChatSession(Base):
    """ORM model for chat_sessions table."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = Column(String(64), primary_key=True, default=_uuid_hex)
    title: Mapped[str | None] = Column(String(255), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    summary: Mapped[str | None] = Column(Text, nullable=True)
    default_kb_ids_json = Column(JSONB, nullable=False, default=list)
    search_mode: Mapped[str] = Column(String(16), nullable=False, default="off")
    model_id: Mapped[str | None] = Column(String(255), nullable=True)
    meta_json = Column(JSONB, nullable=False, default=dict)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    """ORM model for chat_messages table."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = Column(String(64), primary_key=True, default=_uuid_hex)
    session_id: Mapped[str] = Column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = Column(String(16), nullable=False)
    content: Mapped[str] = Column(Text, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

