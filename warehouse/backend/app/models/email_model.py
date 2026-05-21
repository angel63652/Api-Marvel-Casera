from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class EmailPriority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EmailClient(Base):
    __tablename__ = "email_clients"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_name = Column(String(255), nullable=False, index=True)
    customer_email = Column(String(255), unique=True, nullable=False, index=True)
    folder_name = Column(String(100), nullable=True)
    gmail_label = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    auto_filter = Column(Boolean, nullable=False, default=True)
    ai_category = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    messages = relationship(
        "EmailMessage",
        back_populates="email_client",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    gmail_message_id = Column(String(255), unique=True, nullable=False, index=True)
    from_email = Column(String(255), nullable=False, index=True)
    to_email = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    body_preview = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ai_category = Column(String(100), nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_priority = Column(SAEnum(EmailPriority), nullable=True, default=EmailPriority.MEDIUM)
    customer_id = Column(Integer, ForeignKey("email_clients.id", ondelete="SET NULL"), nullable=True)
    folder_assigned = Column(String(100), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    is_notified = Column(Boolean, nullable=False, default=False)
    office_notified_at = Column(DateTime(timezone=True), nullable=True)
    office_notified_to = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    email_client = relationship("EmailClient", back_populates="messages", lazy="selectin")
