"""Smart insights from your own history: bill forecasts, unusual-bill alerts and a month-end projection.
Plain statistics (linear trend, averages), so they are explainable and need no external service."""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bill import BillOccurrence, BillPayment, BillTemplate
from app.schemas.insights import BillInsight, InsightsOut, SpendingInsight
from app.services import expenses as expense_svc

TWO = Decimal("0.01")
MIN_PAYMENTS = 3  # forecasting from fewer points would just be guessing
ALERT_PCT = 25.0  # flag a bill that is this much above its usual amount
MAX_HISTORY = 6


def _money(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)


def linear_forecast(values: list[float]) -> float:
    """Fit a straight line through the points (oldest first) and extend it one step."""
    n = len(values)
    xs = range(n)
    mx, my = (n - 1) / 2, sum(values) / n
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, values)) / denom if denom else 0.0
    return max(0.0, my + slope * (n - mx))


def bill_insights(db: Session, user_id: int) -> list[BillInsight]:
    results = []
    templates = db.scalars(
        select(BillTemplate).where(BillTemplate.user_id == user_id, BillTemplate.is_active.is_(True)).order_by(BillTemplate.name)
    ).all()
    for t in templates:
        rows = db.execute(
            select(BillPayment.amount)
            .join(BillOccurrence, BillPayment.occurrence_id == BillOccurrence.id)
            .where(BillOccurrence.template_id == t.id)
            .order_by(BillOccurrence.due_date)
        ).all()
        amounts = [float(r[0]) for r in rows][-MAX_HISTORY:]
        if len(amounts) < MIN_PAYMENTS:
            continue
        earlier, latest = amounts[:-1], amounts[-1]
        average = sum(earlier) / len(earlier)
        pct = (latest - average) / average * 100 if average else 0.0
        alert = None
        if pct >= ALERT_PCT:
            alert = f"{t.name} was {round(pct)}% higher than usual last time ({_money(latest)} vs about {_money(average)})"
        results.append(BillInsight(
            bill_id=t.id, bill_name=t.name, payments_used=len(amounts), last_paid=_money(latest),
            average=_money(average), forecast_next=_money(linear_forecast(amounts)),
            change_vs_average_pct=round(pct, 1), alert=alert,
        ))
    return results


def spending_insight(db: Session, user_id: int, today: date) -> SpendingInsight:
    summary = expense_svc.build_summary(db, user_id, today.year, today.month)
    last = summary.previous_month_total
    spent = summary.total
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    projected = _money(float(spent) / today.day * days_in_month) if today.day >= 3 and spent > 0 else None
    change = round(float(spent - last) / float(last) * 100, 1) if last > 0 else None
    notes = []
    if projected is not None:
        notes.append(f"At this pace you will spend about {projected} by the end of the month")
    py, pm = expense_svc.previous_month(today.year, today.month)
    prev_by_cat = {c.category: c.total for c in expense_svc.build_summary(db, user_id, py, pm).by_category}
    for c in summary.by_category:
        before = prev_by_cat.get(c.category)
        if before and before > 0 and c.total >= before * Decimal("1.5") and c.total - before >= 500:
            notes.append(f"{c.category.title()} spending is up {round(float(c.total / before - 1) * 100)}% on last month")
    return SpendingInsight(
        month=summary.month, spent_so_far=spent, projected_total=projected, last_month_total=last,
        change_vs_last_month_pct=change, top_category=summary.by_category[0].category if summary.by_category else None,
        notes=notes,
    )


def build_insights(db: Session, user_id: int, today: date) -> InsightsOut:
    bills = bill_insights(db, user_id)
    spending = spending_insight(db, user_id, today)
    highlights = [b.alert for b in bills if b.alert] + spending.notes
    return InsightsOut(highlights=highlights, bills=bills, spending=spending)
