import datetime as dt
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.bill import Money
from app.schemas.expense import ExpenseCategory


class TicketType(str, Enum):
    FLIGHT = "FLIGHT"
    TRAIN = "TRAIN"
    BUS = "BUS"
    EVENT = "EVENT"
    HOTEL = "HOTEL"
    OTHER = "OTHER"


class SplitType(str, Enum):
    EQUAL = "EQUAL"
    CUSTOM = "CUSTOM"


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str
    user_id: int | None


class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    destination: str = Field(default="", max_length=120)
    start_date: date
    end_date: date
    budget: Money | None = None
    description: str | None = Field(default=None, max_length=1000)
    member_names: list[str] = Field(default_factory=list, max_length=30)  # besides you

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class TripUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    budget: Money | None = None
    description: str | None = Field(default=None, max_length=1000)


class TripSummary(BaseModel):
    id: int
    name: str
    destination: str
    start_date: date
    end_date: date
    status: str  # UPCOMING / ONGOING / PAST
    budget: Decimal | None
    total_spent: Decimal
    member_count: int


class TripOut(TripSummary):
    description: str | None
    members: list[MemberOut]


class ItineraryCreate(BaseModel):
    day: date
    time: dt.time | None = None
    title: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=500)


class ItineraryOut(ItineraryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TicketCreate(BaseModel):
    type: TicketType = TicketType.OTHER
    provider: str | None = Field(default=None, max_length=100)
    booking_ref: str | None = Field(default=None, max_length=60)
    cost: Money | None = None
    starts_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    provider: str | None
    booking_ref: str | None
    cost: Decimal | None
    starts_at: datetime | None
    notes: str | None


class ShareIn(BaseModel):
    member_id: int
    amount: Money


class TripExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    category: ExpenseCategory = ExpenseCategory.OTHER
    amount: Money
    paid_by_member_id: int
    spent_on: date | None = None  # defaults to today
    split_type: SplitType = SplitType.EQUAL
    participant_ids: list[int] | None = None  # EQUAL: who shares it (default: everyone)
    shares: list[ShareIn] | None = None  # CUSTOM: exact amount per person, must add up to amount


class ShareOut(BaseModel):
    member_id: int
    member_name: str
    share_amount: Decimal


class TripExpenseOut(BaseModel):
    id: int
    title: str
    category: str
    amount: Decimal
    paid_by_member_id: int
    paid_by_name: str
    spent_on: date
    split_type: str
    shares: list[ShareOut]


class SettlementCreate(BaseModel):
    from_member_id: int
    to_member_id: int
    amount: Money
    settled_on: date | None = None


class SettlementOut(BaseModel):
    id: int
    from_member_id: int
    from_name: str
    to_member_id: int
    to_name: str
    amount: Decimal
    settled_on: date


class BalanceRow(BaseModel):
    member_id: int
    name: str
    paid: Decimal  # what they actually paid out
    share: Decimal  # what they should have paid
    settlements_sent: Decimal
    settlements_received: Decimal
    balance: Decimal  # positive = is owed money, negative = owes money


class SuggestedPayment(BaseModel):
    from_member_id: int
    from_name: str
    to_member_id: int
    to_name: str
    amount: Decimal


class SettlementReport(BaseModel):
    total_spent: Decimal
    balances: list[BalanceRow]
    suggested_payments: list[SuggestedPayment]
