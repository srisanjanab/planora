from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.bill import Money


class GroceryCategory(str, Enum):
    VEGETABLES = "VEGETABLES"
    FRUITS = "FRUITS"
    DAIRY = "DAIRY"
    GRAINS = "GRAINS"
    SNACKS = "SNACKS"
    HOUSEHOLD = "HOUSEHOLD"
    PERSONAL_CARE = "PERSONAL_CARE"
    OTHER = "OTHER"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GroceryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: GroceryCategory = GroceryCategory.OTHER
    quantity: str = Field(default="1", min_length=1, max_length=50)
    estimated_price: Money | None = None
    priority: Priority = Priority.MEDIUM
    notes: str | None = Field(default=None, max_length=300)


class GroceryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: GroceryCategory | None = None
    quantity: str | None = Field(default=None, min_length=1, max_length=50)
    estimated_price: Money | None = None
    priority: Priority | None = None
    notes: str | None = Field(default=None, max_length=300)
    is_bought: bool | None = None  # the checkbox


class GroceryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    quantity: str
    estimated_price: Decimal | None
    priority: str
    notes: str | None
    is_bought: bool
    bought_at: datetime | None
    created_at: datetime


class GrocerySummary(BaseModel):
    remaining: int
    bought: int
    estimated_remaining_cost: Decimal


class ClearResult(BaseModel):
    archived: int
