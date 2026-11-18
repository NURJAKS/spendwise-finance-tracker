import re
from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_AMOUNT = 1_000_000_000


def _validate_hex_color(v: str) -> str:
    val = v.strip()
    if not HEX_COLOR_RE.match(val):
        raise ValueError("Цвет должен быть в формате HEX, например #4F8EF7")
    return val.upper()


def _validate_non_empty(v: str, label: str = "Название") -> str:
    val = v.strip()
    if not val:
        raise ValueError(f"{label} не может быть пустым")
    return val


def _validate_positive_amount(v: int) -> int:
    if v <= 0:
        raise ValueError("Сумма должна быть больше 0")
    if v > MAX_AMOUNT:
        raise ValueError("Сумма слишком велика")
    return v


# --- Categories ---

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=48)
    type: Literal["income", "expense"]
    color: str
    icon: str = Field(default="tag", max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_non_empty(v, "Название категории")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v)

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, v: str) -> str:
        return v.strip() or "tag"


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=48)
    color: Optional[str] = None
    icon: Optional[str] = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_non_empty(v, "Название категории") if v is not None else None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v) if v is not None else None


class CategoryOut(CategoryBase):
    id: int
    is_default: bool = False

    model_config = ConfigDict(from_attributes=True)


# --- Accounts / Wallets ---

class AccountBase(BaseModel):
    name: str = Field(..., max_length=48)
    type: Literal["card", "cash", "savings"] = "card"
    color: str = "#6C7CFF"
    icon: str = Field(default="card", max_length=32)
    initial_balance: int = Field(default=0, ge=-MAX_AMOUNT, le=MAX_AMOUNT)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_non_empty(v, "Название счёта")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v)


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=48)
    type: Optional[Literal["card", "cash", "savings"]] = None
    color: Optional[str] = None
    icon: Optional[str] = Field(default=None, max_length=32)
    initial_balance: Optional[int] = Field(default=None, ge=-MAX_AMOUNT, le=MAX_AMOUNT)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_non_empty(v, "Название счёта") if v is not None else None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v) if v is not None else None


class AccountOut(AccountBase):
    id: int
    is_default: bool = False
    current_balance: int = 0

    model_config = ConfigDict(from_attributes=True)


class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: int
    date: date
    note: Optional[str] = Field(default=None, max_length=100)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        return _validate_positive_amount(v)


# --- Transactions ---

class TransactionBase(BaseModel):
    type: Literal["income", "expense"]
    amount: int
    category_id: int
    account_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=100)
    date: date

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        return _validate_positive_amount(v)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if len(cleaned) > 100:
            raise ValueError("Заметка не должна превышать 100 символов")
        return cleaned


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[int] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=100)
    date: Optional[date] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[int]) -> Optional[int]:
        return _validate_positive_amount(v) if v is not None else None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if len(cleaned) > 100:
            raise ValueError("Заметка не должна превышать 100 символов")
        return cleaned


class TransactionOut(BaseModel):
    id: int
    type: str
    amount: int
    category_id: int
    category_name: str
    category_color: Optional[str] = None
    category_icon: str = "tag"
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    note: Optional[str] = None
    date: date
    is_transfer: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ImportTransactionItem(BaseModel):
    type: Literal["income", "expense"]
    amount: int
    category_id: int
    account_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=100)
    date: date

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        return _validate_positive_amount(v)


class ImportBatchRequest(BaseModel):
    items: List[ImportTransactionItem] = Field(..., min_length=1, max_length=500)


class ImportResultOut(BaseModel):
    imported: int
    skipped: int


class CategorySuggestionOut(BaseModel):
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    confidence: str = "none"


# --- Summary & Analytics ---

class SummaryOut(BaseModel):
    period_start: str
    period_end: str
    income: int
    expense: int
    balance: int
    prev_income: int = 0
    prev_expense: int = 0
    prev_balance: int = 0
    expense_change_pct: Optional[float] = None
    income_change_pct: Optional[float] = None
    safe_daily_spend: Optional[int] = None
    days_remaining: int = 0


class CategoryStatOut(BaseModel):
    category_id: int
    name: str
    color: str
    icon: str = "tag"
    total: int
    percent: float


class ComparisonSeriesOut(BaseModel):
    period: Literal["day", "week", "month"]
    type: Literal["income", "expense"]
    mode: Literal["timeline", "category"]
    current_label: str
    previous_label: str
    labels: List[str]
    current_daily: List[Optional[int]]
    previous_daily: List[Optional[int]]
    current_cumulative: List[Optional[int]]
    previous_cumulative: List[Optional[int]]
    current_total: int
    previous_total: int
    pace_current_total: int
    pace_previous_total: int
    delta_pct: Optional[float] = None


class ForecastHistoryPoint(BaseModel):
    month: str
    label: str
    actual_expense: int
    actual_income: int
    projected_expense: Optional[int] = None
    is_current: bool = False
    is_forecast: bool = False


class ForecastCategoryOut(BaseModel):
    category_id: int
    name: str
    color: str
    icon: str
    avg_monthly: int
    current_month: int
    forecast_next_month: int
    budget_limit: Optional[int] = None
    share_pct: float


class ForecastOut(BaseModel):
    current_month: str
    current_month_label: str
    target_month: str
    target_month_label: str
    current_month_actual: int
    current_month_projected: int
    forecast_next_month: int
    forecast_low: int
    forecast_high: int
    expected_income: int
    expected_savings: int
    trend_percent: float
    months_analyzed: int
    confidence: Literal["high", "medium", "low"]
    history: List[ForecastHistoryPoint]
    by_category: List[ForecastCategoryOut]
    insights: List[str]


# --- Budgets ---

class BudgetUpsert(BaseModel):
    category_id: int
    month: str
    limit_amount: int = Field(..., ge=0, le=MAX_AMOUNT)

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("Месяц должен быть в формате YYYY-MM")
        return v


class BudgetCategoryStatusOut(BaseModel):
    budget_id: Optional[int] = None
    category_id: int
    category_name: str
    category_color: str
    category_icon: str
    month: str
    limit_amount: Optional[int] = None
    spent: int
    remaining: Optional[int] = None
    percent: Optional[float] = None
    status: Literal["unset", "ok", "warning", "exceeded"]


class BudgetsOverviewOut(BaseModel):
    month: str
    total_limit: int
    total_spent: int
    safe_daily_spend: Optional[int] = None
    days_remaining: int
    items: List[BudgetCategoryStatusOut]


# --- Recurring Rules ---

class RecurringBase(BaseModel):
    type: Literal["income", "expense"]
    amount: int
    category_id: int
    account_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=100)
    day_of_month: int = Field(default=1, ge=1, le=31)
    is_active: bool = True

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        return _validate_positive_amount(v)


class RecurringCreate(RecurringBase):
    pass


class RecurringUpdate(BaseModel):
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[int] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=100)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    is_active: Optional[bool] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[int]) -> Optional[int]:
        return _validate_positive_amount(v) if v is not None else None


class RecurringOut(RecurringBase):
    id: int
    category_name: str
    category_color: str
    category_icon: str
    account_name: Optional[str] = None
    last_applied_month: Optional[str] = None
    applied_current_month: bool = False


class RecurringApplyOut(BaseModel):
    month: str
    created_count: int


# --- Savings Goals ---

class GoalCreate(BaseModel):
    name: str = Field(..., max_length=80)
    target_amount: int
    current_amount: int = Field(default=0, ge=0, le=MAX_AMOUNT)
    deadline: Optional[date] = None
    color: str = "#34C38F"
    icon: str = Field(default="target", max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_non_empty(v, "Название цели")

    @field_validator("target_amount")
    @classmethod
    def validate_target(cls, v: int) -> int:
        return _validate_positive_amount(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _validate_hex_color(v)


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    target_amount: Optional[int] = None
    deadline: Optional[date] = None
    color: Optional[str] = None
    icon: Optional[str] = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_non_empty(v, "Название цели") if v is not None else None

    @field_validator("target_amount")
    @classmethod
    def validate_target(cls, v: Optional[int]) -> Optional[int]:
        return _validate_positive_amount(v) if v is not None else None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v) if v is not None else None


class GoalContribute(BaseModel):
    delta: int = Field(..., ge=-MAX_AMOUNT, le=MAX_AMOUNT)

    @field_validator("delta")
    @classmethod
    def non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Сумма изменения должна быть не равна 0")
        return v


class GoalOut(BaseModel):
    id: int
    name: str
    target_amount: int
    current_amount: int
    deadline: Optional[date] = None
    color: str
    icon: str
    percent: float
    remaining: int
    is_completed: bool
