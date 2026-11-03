from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bill import BillOccurrence, BillPayment, BillTemplate
from app.models.expense import Expense
from app.models.user import User
from app.schemas.dashboard import BillsCard, DashboardOut, ExpensesCard
from app.schemas.expense import ExpenseOut
from app.services import bills as bill_svc
from app.services import expenses as expense_svc
from app.services import grocery as grocery_svc

ZERO = Decimal("0.00")


def _bills_card(db: Session, user: User, today: date) -> BillsCard:
    bill_svc.ensure_occurrences(db, user.id)
    pending = db.scalars(
        select(BillOccurrence)
        .join(BillTemplate)
        .where(
            BillTemplate.user_id == user.id,
            BillTemplate.is_active.is_(True),
            BillOccurrence.status == "PENDING",
        )
        .order_by(BillOccurrence.due_date, BillOccurrence.id)
    ).all()
    outs = [bill_svc.occurrence_to_out(o, today) for o in pending]
    reminders = [o for o in outs if o.status in ("DUE", "OVERDUE")]
    upcoming = [o for o in outs if o.status == "UPCOMING"]

    first, last = expense_svc.month_bounds(today.year, today.month)
    paid = db.scalar(
        select(func.coalesce(func.sum(BillPayment.amount), 0))
        .join(BillOccurrence, BillPayment.occurrence_id == BillOccurrence.id)
        .join(BillTemplate, BillOccurrence.template_id == BillTemplate.id)
        .where(BillTemplate.user_id == user.id, BillPayment.paid_on >= first, BillPayment.paid_on <= last)
    )
    return BillsCard(
        reminder_count=len(reminders),
        overdue_count=sum(1 for o in reminders if o.status == "OVERDUE"),
        amount_due=sum((o.expected_amount for o in reminders), ZERO),
        paid_this_month=Decimal(paid).quantize(ZERO),
        reminders=reminders[:10],
        upcoming=upcoming[:5],
    )


def _expenses_card(db: Session, user: User, today: date) -> ExpensesCard:
    total, count = expense_svc.month_total(db, user.id, today.year, today.month)
    recent = db.scalars(
        select(Expense)
        .where(Expense.user_id == user.id)
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .limit(5)
    ).all()
    return ExpensesCard(
        month=f"{today.year:04d}-{today.month:02d}",
        month_total=total,
        month_count=count,
        recent=[ExpenseOut.model_validate(e) for e in recent],
    )


def build_dashboard(db: Session, user: User, today: date) -> DashboardOut:
    return DashboardOut(
        today=today.isoformat(),
        bills=_bills_card(db, user, today),
        expenses=_expenses_card(db, user, today),
        grocery=grocery_svc.build_summary(db, user.id),
    )
