from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(80), default="")
    gateway_id: Mapped[str] = mapped_column(String(80), default="")
    bank_id: Mapped[str] = mapped_column(String(80), default="")
    order_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    gateway_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    bank_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_date: Mapped[str] = mapped_column(String(40), default="")
    gateway_date: Mapped[str] = mapped_column(String(40), default="")
    bank_date: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="UNRESOLVED")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    signals: Mapped[str] = mapped_column(Text, default="")
    exception_type: Mapped[str] = mapped_column(String(80), default="")
    severity: Mapped[str] = mapped_column(String(20), default="")
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    amount_at_risk: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class ExceptionRecord(Base):
    __tablename__ = "exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[str] = mapped_column(String(80), default="")
    exception_type: Mapped[str] = mapped_column(String(80), default="UNRESOLVED")
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    expected_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    amount_at_risk: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exception_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100), default="")
    actor: Mapped[str] = mapped_column(String(40), default="SYSTEM")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
