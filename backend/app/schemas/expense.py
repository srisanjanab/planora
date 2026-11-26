from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.bill import Money, PaymentMethod


class ExpenseCategory(str, Enum):
    FOOD = "FOOD"
    TRAVEL = "TRAVEL"
    SHOPPING = "SHOPPING"
    EDUCATION = "EDUCATION"
    HEALTH = "HEALTH"
    ENTERTAINMENT = "ENTERTAINMENT"
    UTILITIES = "UTILITIES"
    OTHER = "OTHER"


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    category: ExpenseCategory = ExpenseCategory.OTHER
    amount: Money
    spent_on: date | None = None  # defaults to today
    payment_method: PaymentMethod | None = None
    note: str | None = Field(default=None, max_length=500)


class ExpenseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    category: ExpenseCategory | None = None
    amount: Money | None = None
    spent_on: date | None = None
    payment_method: PaymentMethod | None = None
    note: str | None = Field(default=None, max_length=500)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    amount: Decimal
    spent_on: date
    payment_method: str | None
    note: str | None
    created_at: datetime


class CategoryTotal(BaseModel):
    category: str
    total: Decimal
    count: int


class ExpenseSummary(BaseModel):
    month: str  # "2026-10"
    total: Decimal
    count: int
    by_category: list[CategoryTotal]  # biggest first
    previous_month_total: Decimal


class AltCategory(BaseModel):
    category: str
    confidence: float


class CategorySuggestion(BaseModel):
    category: str
    confidence: float  # 0..1
    confident: bool  # True when the frontend should auto-fill it
    source: str  # "history" (you used this title before) or "model"
    alternatives: list[AltCategory]
