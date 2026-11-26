from decimal import Decimal

from pydantic import BaseModel


class BillInsight(BaseModel):
    bill_id: int
    bill_name: str
    payments_used: int
    last_paid: Decimal
    average: Decimal  # average of the earlier payments
    forecast_next: Decimal  # predicted amount of the next cycle
    change_vs_average_pct: float
    alert: str | None  # e.g. "Electricity was 38% higher than usual"


class SpendingInsight(BaseModel):
    month: str
    spent_so_far: Decimal
    projected_total: Decimal | None  # month-end estimate at the current pace
    last_month_total: Decimal
    change_vs_last_month_pct: float | None
    top_category: str | None
    notes: list[str]


class InsightsOut(BaseModel):
    highlights: list[str]  # the short sentences worth showing on the dashboard
    bills: list[BillInsight]
    spending: SpendingInsight
