from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    loyalty_tier: Mapped[str] = mapped_column(String, nullable=False)
    account_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    total_spent: Mapped[float] = mapped_column(Float, nullable=False)
    fraud_risk: Mapped[str] = mapped_column(String, default="LOW", nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_date: Mapped[Date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[Date] = mapped_column(Date, nullable=False)
    final_sale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    returned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String, default="delivered", nullable=False)
    condition_note: Mapped[str] = mapped_column(String, default="original", nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="orders")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="OPEN", nullable=False)
    latest_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    trace_events: Mapped[list["TraceEvent"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    step: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    severity: Mapped[str] = mapped_column(String, default="info", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="trace_events")


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True, nullable=False)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

