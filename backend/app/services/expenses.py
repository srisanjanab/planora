import calendar
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.schemas.expense import AltCategory, CategorySuggestion, CategoryTotal, ExpenseSummary

ZERO = Decimal("0.00")


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def parse_month(value: str | None, today: date) -> tuple[int, int]:
    """'2026-10' -> (2026, 10). None -> the current month."""
    if value is None:
        return today.year, today.month
    try:
        year_s, month_s = value.split("-")
        year, month = int(year_s), int(month_s)
        date(year, month, 1)
    except ValueError:
        raise HTTPException(status_code=422, detail="month must look like 2026-10")
    return year, month


def previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def month_total(db: Session, user_id: int, year: int, month: int) -> tuple[Decimal, int]:
    first, last = month_bounds(year, month)
    total, count = db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id)).where(
            Expense.user_id == user_id, Expense.spent_on >= first, Expense.spent_on <= last
        )
    ).one()
    return Decimal(total).quantize(ZERO), count


def build_summary(db: Session, user_id: int, year: int, month: int) -> ExpenseSummary:
    first, last = month_bounds(year, month)
    rows = db.execute(
        select(Expense.category, func.sum(Expense.amount), func.count(Expense.id))
        .where(Expense.user_id == user_id, Expense.spent_on >= first, Expense.spent_on <= last)
        .group_by(Expense.category)
    ).all()
    by_category = sorted(
        (CategoryTotal(category=c, total=Decimal(t).quantize(ZERO), count=n) for c, t, n in rows),
        key=lambda x: x.total,
        reverse=True,
    )
    total, count = month_total(db, user_id, year, month)
    prev_total, _ = month_total(db, user_id, *previous_month(year, month))
    return ExpenseSummary(
        month=f"{year:04d}-{month:02d}",
        total=total,
        count=count,
        by_category=by_category,
        previous_month_total=prev_total,
    )


CONFIDENCE_THRESHOLD = 0.5


def suggest_category(db: Session, user_id: int, title: str) -> CategorySuggestion:
    """1) If you categorised this exact title before, reuse that (it learns from you).
    2) Otherwise ask the ML model, and only call it 'confident' above the threshold."""
    from app.ml import categorizer  # imported lazily so the API starts fast

    title = title.strip()
    past = db.scalar(
        select(Expense)
        .where(Expense.user_id == user_id, func.lower(Expense.title) == title.lower())
        .order_by(Expense.id.desc())
        .limit(1)
    )
    if past:
        return CategorySuggestion(category=past.category, confidence=1.0, confident=True, source="history", alternatives=[])
    ranked = categorizer.predict(title, 3)
    best, conf = ranked[0]
    return CategorySuggestion(
        category=best, confidence=conf, confident=conf >= CONFIDENCE_THRESHOLD, source="model",
        alternatives=[AltCategory(category=c, confidence=p) for c, p in ranked[1:]],
    )
