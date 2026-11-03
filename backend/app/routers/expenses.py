from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, get_today
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    ExpenseCategory,
    ExpenseCreate,
    ExpenseOut,
    ExpenseSummary,
    ExpenseUpdate,
)
from app.schemas.bill import PaymentMethod
from app.services import expenses as svc

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_expense(db: Session, user: User, expense_id: int) -> Expense:
    exp = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if exp is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return exp


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    exp = Expense(
        user_id=user.id,
        title=data.title.strip(),
        category=data.category.value,
        amount=data.amount,
        spent_on=data.spent_on or today,
        payment_method=data.payment_method.value if data.payment_method else None,
        note=data.note,
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    date_from: date | None = None,
    date_to: date | None = None,
    category: ExpenseCategory | None = None,
    payment_method: PaymentMethod | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Expense).where(Expense.user_id == user.id)
    if date_from:
        query = query.where(Expense.spent_on >= date_from)
    if date_to:
        query = query.where(Expense.spent_on <= date_to)
    if category:
        query = query.where(Expense.category == category.value)
    if payment_method:
        query = query.where(Expense.payment_method == payment_method.value)
    query = query.order_by(Expense.spent_on.desc(), Expense.id.desc()).limit(limit).offset(offset)
    return db.scalars(query).all()


# NOTE: /summary must be declared before /{expense_id}, or "summary" would be read as an id.
@router.get("/summary", response_model=ExpenseSummary)
def expense_summary(
    month: str | None = Query(default=None, description="YYYY-MM, defaults to the current month"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    today: date = Depends(get_today),
):
    year, mon = svc.parse_month(month, today)
    return svc.build_summary(db, user.id, year, mon)


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_expense(db, user, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exp = _get_expense(db, user, expense_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("category", "payment_method") and value is not None:
            value = value.value
        if field in ("title", "amount", "spent_on", "category") and value is None:
            continue  # these cannot be cleared
        setattr(exp, field, value)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_get_expense(db, user, expense_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
