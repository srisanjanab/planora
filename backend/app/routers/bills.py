from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, get_today
from app.models.bill import BillOccurrence, BillTemplate
from app.models.user import User
from app.schemas.bill import BillCreate, BillOut, BillUpdate, OccurrenceOut, PayRequest
from app.services import bills as svc

bills_router = APIRouter(prefix="/bills", tags=["bills"])
occurrences_router = APIRouter(prefix="/occurrences", tags=["bills"])


def _get_bill(db: Session, user: User, bill_id: int) -> BillTemplate:
    """Another user's bill looks exactly like a missing one: 404, never 403."""
    bill = db.scalar(select(BillTemplate).where(BillTemplate.id == bill_id, BillTemplate.user_id == user.id))
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def _get_occurrence(db: Session, user: User, occ_id: int) -> BillOccurrence:
    occ = db.scalar(
        select(BillOccurrence)
        .join(BillTemplate)
        .where(BillOccurrence.id == occ_id, BillTemplate.user_id == user.id)
    )
    if occ is None:
        raise HTTPException(status_code=404, detail="Bill cycle not found")
    return occ


# ---------- /bills ----------

@bills_router.post("", response_model=BillOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    data: BillCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    return svc.template_to_out(svc.create_template(db, user, data), today)


@bills_router.get("", response_model=list[BillOut])
def list_bills(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    svc.ensure_occurrences(db, user.id)
    query = select(BillTemplate).where(BillTemplate.user_id == user.id).order_by(BillTemplate.name)
    if not include_inactive:
        query = query.where(BillTemplate.is_active.is_(True))
    return [svc.template_to_out(t, today) for t in db.scalars(query).all()]


@bills_router.get("/{bill_id}", response_model=BillOut)
def get_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    return svc.template_to_out(_get_bill(db, user, bill_id), today)


@bills_router.patch("/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: int,
    data: BillUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    bill = svc.update_template(db, _get_bill(db, user, bill_id), data)
    return svc.template_to_out(bill, today)


@bills_router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(bill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Deletes the bill AND its whole history. To stop a bill but keep history, PATCH is_active=false."""
    db.delete(_get_bill(db, user, bill_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@bills_router.get("/{bill_id}/occurrences", response_model=list[OccurrenceOut])
def bill_history(
    bill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    bill = _get_bill(db, user, bill_id)
    return [svc.occurrence_to_out(o, today) for o in reversed(bill.occurrences)]  # newest first


# ---------- /occurrences ----------

StatusFilter = Literal["UPCOMING", "DUE", "OVERDUE", "PAID", "SKIPPED", "REMINDERS"]


@occurrences_router.get("", response_model=list[OccurrenceOut])
def list_occurrences(
    status_filter: StatusFilter | None = Query(default=None, alias="status"),
    bill_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    """status_filter=REMINDERS returns what the dashboard should nag about: unpaid cycles
    whose reminder date has arrived (DUE + OVERDUE)."""
    svc.ensure_occurrences(db, user.id)
    query = (
        select(BillOccurrence)
        .join(BillTemplate)
        .where(BillTemplate.user_id == user.id)
        .order_by(BillOccurrence.due_date, BillOccurrence.id)
    )
    if bill_id is not None:
        query = query.where(BillOccurrence.template_id == bill_id)
    result = []
    for occ in db.scalars(query).all():
        out = svc.occurrence_to_out(occ, today)
        wanted = {"DUE", "OVERDUE"} if status_filter == "REMINDERS" else {status_filter}
        if status_filter is None or out.status in wanted:
            result.append(out)
    return result


@occurrences_router.post("/{occ_id}/pay", response_model=OccurrenceOut)
def pay(
    occ_id: int,
    data: PayRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    occ = svc.pay_occurrence(db, _get_occurrence(db, user, occ_id), data or PayRequest(), today)
    return svc.occurrence_to_out(occ, today)


@occurrences_router.post("/{occ_id}/skip", response_model=OccurrenceOut)
def skip(
    occ_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    return svc.occurrence_to_out(svc.skip_occurrence(db, _get_occurrence(db, user, occ_id)), today)


@occurrences_router.post("/{occ_id}/undo", response_model=OccurrenceOut)
def undo(
    occ_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    return svc.occurrence_to_out(svc.undo_occurrence(db, _get_occurrence(db, user, occ_id)), today)
