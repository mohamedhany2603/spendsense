import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    categorized = "categorized"
    failed = "failed"


class CategorizeSource(str, enum.Enum):
    manual = "manual"
    llm = "llm"
    rule = "rule"
    cache = "cache"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )

    merchant: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.pending, index=True
    )
    source: Mapped[CategorizeSource | None] = mapped_column(
        Enum(CategorizeSource), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    categorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")


class ClassifierCache(Base):
    """Cached LLM/rule results per normalized merchant. Expensive result, reused."""

    __tablename__ = "classifier_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    source: Mapped[str] = mapped_column(String(16), default="rule")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped["Category"] = relationship()


class LlmCostLog(Base):
    """Every LLM call is logged with its token usage and estimated cost."""

    __tablename__ = "llm_cost_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    merchant: Mapped[str] = mapped_column(String(255))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    response_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)  # e.g. "2026-08"
    file_name: Mapped[str] = mapped_column(String(255))
    total_expense: Mapped[float] = mapped_column(Float, default=0.0)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship()