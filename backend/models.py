from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(48), index=True, nullable=False)
    type = Column(String(16), index=True, nullable=False)
    color = Column(String(16), nullable=False)
    icon = Column(String(32), nullable=False, default="tag")
    is_default = Column(Boolean, nullable=False, default=False)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(48), nullable=False)
    type = Column(String(16), nullable=False, default="card")
    color = Column(String(16), nullable=False, default="#6C7CFF")
    icon = Column(String(32), nullable=False, default="card")
    initial_balance = Column(Integer, nullable=False, default=0)
    is_default = Column(Boolean, nullable=False, default=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(16), index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), index=True, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True, nullable=True)
    note = Column(String(100), nullable=True)
    date = Column(Date, index=True, nullable=False)
    is_transfer = Column(Boolean, index=True, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    category = relationship("Category")
    account = relationship("Account")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", name="uq_budget_category_month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), index=True, nullable=False)
    month = Column(String(7), index=True, nullable=False)
    limit_amount = Column(Integer, nullable=False)

    category = relationship("Category")


class RecurringRule(Base):
    __tablename__ = "recurring_rules"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(16), nullable=False)
    amount = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    note = Column(String(100), nullable=True)
    day_of_month = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    last_applied_month = Column(String(7), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    category = relationship("Category")
    account = relationship("Account")


class SavingsGoal(Base):
    __tablename__ = "savings_goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    target_amount = Column(Integer, nullable=False)
    current_amount = Column(Integer, nullable=False, default=0)
    deadline = Column(Date, nullable=True)
    color = Column(String(16), nullable=False, default="#34C38F")
    icon = Column(String(32), nullable=False, default="target")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
