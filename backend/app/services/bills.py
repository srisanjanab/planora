"""Business logic for recurring bills. Routers stay thin; the rules live here."""
import calendar
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bill import BillOccurrence, BillPayment, BillTemplate
from app.models.user import User
from app.schemas.bill import BillCreate, BillOut, BillUpdate, Frequency, OccurrenceOut, PayRequest


# ---------- date helpers ----------

def add_months(d: date, months: int, anchor_day: int) -> date:
    """Move d forward by N months, using anchor_day clamped to the month's length
    (anchor 31 -> Feb 28/29, Apr 30, ...)."""
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last_day))


def next_due_date(prev_due: date, frequency: str, anchor_day: int) -> date:
    freq = Frequency(frequency)
    if freq == Frequency.WEEKLY:
        return prev_due + timedelta(days=7)
    if freq == Frequency.MONTHLY:
        return add_months(prev_due, 1, anchor_day)
    return add_months(prev_due, 12, anchor_day)


def compute_status(occ: BillOccurrence, today: date) -> str:
    if occ.status in ("PAID", "SKIPPED"):
        return occ.status
    if today > occ.due_date:
        return "OVERDUE"
    if today >= occ.reminder_date:
        return "DUE"
    return "UPCOMING"


# ---------- output builders ----------

def occurrence_to_out(occ: BillOccurrence, today: date) -> OccurrenceOut:
    pay = occ.payment
    return OccurrenceOut(
        id=occ.id,
        bill_id=occ.template_id,
        bill_name=occ.template.name,
        bill_type=occ.template.type,
        due_date=occ.due_date,
        reminder_date=occ.reminder_date,
        expected_amount=occ.expected_amount,
        status=compute_status(occ, today),
        paid_amount=pay.amount if pay else None,
        paid_on=pay.paid_on if pay else None,
        payment_method=pay.payment_method if pay else None,
        note=pay.note if pay else None,
    )


def template_to_out(t: BillTemplate, today: date) -> BillOut:
    out = BillOut.model_validate(t)
    nxt = next((o for o in t.occurrences if o.status == "PENDING"), None)
    out.next_occurrence = occurrence_to_out(nxt, today) if nxt else None
    return out


# ---------- occurrence creation ----------

def _new_occurrence(t: BillTemplate, due: date) -> BillOccurrence:
    return BillOccurrence(
        template_id=t.id,
        due_date=due,
        reminder_date=due - timedelta(days=t.reminder_days_before),
        expected_amount=t.default_amount,
        status="PENDING",
    )


def schedule_next(db: Session, t: BillTemplate, after_due: date) -> BillOccurrence | None:
    """Create the cycle after `after_due`. Safe to call twice: it never creates duplicates."""
    if not t.is_active or not t.auto_create_next:
        return None
    due = next_due_date(after_due, t.frequency, t.first_due_date.day)
    existing = db.scalar(
        select(BillOccurrence).where(BillOccurrence.template_id == t.id, BillOccurrence.due_date == due)
    )
    if existing:
        return existing
    occ = _new_occurrence(t, due)
    db.add(occ)
    db.flush()
    return occ


def ensure_occurrences(db: Session, user_id: int) -> None:
    """Safety net: if an active template has no pending cycle (e.g. user turned auto-create
    on later), create the next one."""
    templates = db.scalars(
        select(BillTemplate).where(
            BillTemplate.user_id == user_id,
            BillTemplate.is_active.is_(True),
            BillTemplate.auto_create_next.is_(True),
        )
    ).all()
    changed = False
    for t in templates:
        if any(o.status == "PENDING" for o in t.occurrences):
            continue
        if t.occurrences:
            schedule_next(db, t, t.occurrences[-1].due_date)
            changed = True
    if changed:
        db.commit()


# ---------- templates ----------

def create_template(db: Session, user: User, data: BillCreate) -> BillTemplate:
    t = BillTemplate(
        user_id=user.id,
        name=data.name.strip(),
        type=data.type.value,
        default_amount=data.default_amount,
        is_variable=data.is_variable,
        frequency=data.frequency.value,
        first_due_date=data.first_due_date,
        reminder_days_before=data.reminder_days_before,
        auto_create_next=data.auto_create_next,
        notes=data.notes,
    )
    db.add(t)
    db.flush()
    db.add(_new_occurrence(t, data.first_due_date))
    db.commit()
    db.refresh(t)
    return t


def update_template(db: Session, t: BillTemplate, data: BillUpdate) -> BillTemplate:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "type" and value is not None:
            value = value.value
        setattr(t, field, value)
    # Keep still-pending cycles in sync; paid history is never touched.
    for occ in t.occurrences:
        if occ.status != "PENDING":
            continue
        if "reminder_days_before" in changes:
            occ.reminder_date = occ.due_date - timedelta(days=t.reminder_days_before)
        if "default_amount" in changes:
            occ.expected_amount = t.default_amount
    db.commit()
    db.refresh(t)
    return t


# ---------- occurrence actions ----------

def pay_occurrence(db: Session, occ: BillOccurrence, data: PayRequest, today: date) -> BillOccurrence:
    if occ.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This bill cycle is already {occ.status}")
    paid_on = data.paid_on or today
    if paid_on > today:
        raise HTTPException(status_code=400, detail="Payment date cannot be in the future")
    db.add(
        BillPayment(
            occurrence_id=occ.id,
            amount=data.amount if data.amount is not None else occ.expected_amount,
            paid_on=paid_on,
            payment_method=data.payment_method.value if data.payment_method else None,
            note=data.note,
        )
    )
    occ.status = "PAID"
    db.flush()
    schedule_next(db, occ.template, occ.due_date)
    db.commit()
    db.refresh(occ)
    return occ


def skip_occurrence(db: Session, occ: BillOccurrence) -> BillOccurrence:
    if occ.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This bill cycle is already {occ.status}")
    occ.status = "SKIPPED"
    db.flush()
    schedule_next(db, occ.template, occ.due_date)
    db.commit()
    db.refresh(occ)
    return occ


def undo_occurrence(db: Session, occ: BillOccurrence) -> BillOccurrence:
    """Undo an accidental Paid / Skip tick. Only allowed while no later cycle has been handled."""
    if occ.status not in ("PAID", "SKIPPED"):
        raise HTTPException(status_code=409, detail="Only a paid or skipped cycle can be undone")
    later = [o for o in occ.template.occurrences if o.due_date > occ.due_date]
    if any(o.status != "PENDING" for o in later):
        raise HTTPException(status_code=409, detail="A later cycle was already paid or skipped")
    for o in later:  # auto-generated next cycle(s): remove so the old one is the single pending one
        db.delete(o)
    if occ.payment:
        db.delete(occ.payment)
    occ.status = "PENDING"
    db.commit()
    db.refresh(occ)
    return occ
