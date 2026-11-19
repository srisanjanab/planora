from decimal import Decimal

from pydantic import BaseModel

from app.schemas.bill import OccurrenceOut
from app.schemas.expense import ExpenseOut
from app.schemas.grocery import GrocerySummary
from app.schemas.trip import TripSummary


class BillsCard(BaseModel):
    reminder_count: int  # unpaid cycles whose reminder date has arrived (DUE + OVERDUE)
    overdue_count: int
    amount_due: Decimal  # sum of expected amounts of those cycles
    paid_this_month: Decimal  # actual bill payments made this month
    reminders: list[OccurrenceOut]  # DUE + OVERDUE, soonest first (max 10)
    upcoming: list[OccurrenceOut]  # next UPCOMING cycles (max 5)


class ExpensesCard(BaseModel):
    month: str
    month_total: Decimal
    month_count: int
    recent: list[ExpenseOut]  # latest 5


class TripsCard(BaseModel):
    upcoming: list[TripSummary]  # ongoing or upcoming trips, soonest first (max 3)


class DashboardOut(BaseModel):
    today: str
    bills: BillsCard
    expenses: ExpensesCard
    grocery: GrocerySummary
    trips: TripsCard
