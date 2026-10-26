from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class BillType(str, Enum):
    INTERNET = "INTERNET"
    MILK = "MILK"
    ELECTRICITY = "ELECTRICITY"
    WATER = "WATER"
    RENT = "RENT"
    SUBSCRIPTION = "SUBSCRIPTION"
    MOBILE = "MOBILE"
    OTHER = "OTHER"


class Frequency(str, Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class PaymentMethod(str, Enum):
    CASH = "CASH"
    UPI = "UPI"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    OTHER = "OTHER"


Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class BillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: BillType = BillType.OTHER
    default_amount: Money
    is_variable: bool = False
    frequency: Frequency = Frequency.MONTHLY
    first_due_date: date
    reminder_days_before: int = Field(default=3, ge=0, le=60)
    auto_create_next: bool = True
    notes: str | None = Field(default=None, max_length=500)


class BillUpdate(BaseModel):
    """All fields optional. Frequency and first_due_date cannot be changed in the MVP."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: BillType | None = None
    default_amount: Money | None = None
    is_variable: bool | None = None
    reminder_days_before: int | None = Field(default=None, ge=0, le=60)
    auto_create_next: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class PayRequest(BaseModel):
    amount: Money | None = None  # defaults to the expected amount
    paid_on: date | None = None  # defaults to today
    payment_method: PaymentMethod | None = None
    note: str | None = Field(default=None, max_length=255)


class OccurrenceOut(BaseModel):
    id: int
    bill_id: int
    bill_name: str
    bill_type: str
    due_date: date
    reminder_date: date
    expected_amount: Decimal
    status: str  # UPCOMING / DUE / OVERDUE / PAID / SKIPPED
    paid_amount: Decimal | None = None
    paid_on: date | None = None
    payment_method: str | None = None
    note: str | None = None


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    default_amount: Decimal
    is_variable: bool
    frequency: str
    first_due_date: date
    reminder_days_before: int
    auto_create_next: bool
    is_active: bool
    notes: str | None
    created_at: datetime
    next_occurrence: OccurrenceOut | None = None
