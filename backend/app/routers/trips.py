from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, get_today
from app.models.trip import ItineraryItem, Settlement, Ticket, Trip, TripExpense
from app.models.user import User
from app.schemas.trip import (
    ItineraryCreate, ItineraryOut, MemberCreate, MemberOut, SettlementCreate, SettlementOut,
    SettlementReport, TicketCreate, TicketOut, TripCreate, TripExpenseCreate, TripExpenseOut,
    TripOut, TripSummary, TripUpdate,
)
from app.services import trips as svc

router = APIRouter(prefix="/trips", tags=["trips"])
NO_CONTENT = status.HTTP_204_NO_CONTENT


def _trip(db: Session, user: User, trip_id: int) -> Trip:
    """Someone else's trip looks exactly like a missing one: 404."""
    t = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == user.id))
    if t is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return t


def _child(items, item_id: int, label: str):
    for i in items:
        if i.id == item_id:
            return i
    raise HTTPException(status_code=404, detail=f"{label} not found")


# ---------- trips ----------

@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(data: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                today: date = Depends(get_today)):
    return svc.trip_out(svc.create_trip(db, user, data), today)


@router.get("", response_model=list[TripSummary])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user),
               today: date = Depends(get_today)):
    rows = db.scalars(select(Trip).where(Trip.owner_id == user.id).order_by(Trip.start_date.desc())).all()
    return [svc.summary(t, today) for t in rows]


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
             today: date = Depends(get_today)):
    return svc.trip_out(_trip(db, user, trip_id), today)


@router.patch("/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int, data: TripUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user), today: date = Depends(get_today)):
    return svc.trip_out(svc.update_trip(db, _trip(db, user, trip_id), data), today)


@router.delete("/{trip_id}", status_code=NO_CONTENT)
def delete_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Deletes the trip with all its expenses, tickets and settlements."""
    db.delete(_trip(db, user, trip_id))
    db.commit()
    return Response(status_code=NO_CONTENT)


# ---------- members ----------

@router.post("/{trip_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(trip_id: int, data: MemberCreate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return svc.add_member(db, _trip(db, user, trip_id), data.display_name)


@router.delete("/{trip_id}/members/{member_id}", status_code=NO_CONTENT)
def remove_member(trip_id: int, member_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc.remove_member(db, _trip(db, user, trip_id), member_id)
    return Response(status_code=NO_CONTENT)


# ---------- itinerary ----------

@router.post("/{trip_id}/itinerary", response_model=ItineraryOut, status_code=status.HTTP_201_CREATED)
def add_itinerary(trip_id: int, data: ItineraryCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return svc.add_itinerary(db, _trip(db, user, trip_id), data)


@router.get("/{trip_id}/itinerary", response_model=list[ItineraryOut])
def list_itinerary(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _trip(db, user, trip_id).itinerary


@router.delete("/{trip_id}/itinerary/{item_id}", status_code=NO_CONTENT)
def delete_itinerary(trip_id: int, item_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    db.delete(_child(_trip(db, user, trip_id).itinerary, item_id, "Itinerary item"))
    db.commit()
    return Response(status_code=NO_CONTENT)


# ---------- tickets ----------

@router.post("/{trip_id}/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def add_ticket(trip_id: int, data: TicketCreate, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return svc.add_ticket(db, _trip(db, user, trip_id), data)


@router.get("/{trip_id}/tickets", response_model=list[TicketOut])
def list_tickets(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _trip(db, user, trip_id).tickets


@router.delete("/{trip_id}/tickets/{ticket_id}", status_code=NO_CONTENT)
def delete_ticket(trip_id: int, ticket_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    db.delete(_child(_trip(db, user, trip_id).tickets, ticket_id, "Ticket"))
    db.commit()
    return Response(status_code=NO_CONTENT)


# ---------- expenses ----------

@router.post("/{trip_id}/expenses", response_model=TripExpenseOut, status_code=status.HTTP_201_CREATED)
def add_expense(trip_id: int, data: TripExpenseCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user), today: date = Depends(get_today)):
    return svc.expense_out(svc.add_expense(db, _trip(db, user, trip_id), data, today))


@router.get("/{trip_id}/expenses", response_model=list[TripExpenseOut])
def list_expenses(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = sorted(_trip(db, user, trip_id).expenses, key=lambda e: (e.spent_on, e.id), reverse=True)
    return [svc.expense_out(e) for e in rows]


@router.delete("/{trip_id}/expenses/{expense_id}", status_code=NO_CONTENT)
def delete_expense(trip_id: int, expense_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    db.delete(_child(_trip(db, user, trip_id).expenses, expense_id, "Expense"))
    db.commit()
    return Response(status_code=NO_CONTENT)


# ---------- balances ----------

@router.get("/{trip_id}/settlement", response_model=SettlementReport)
def settlement(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Who paid, who owes, and the fewest payments that settle everyone up."""
    return svc.settlement_report(_trip(db, user, trip_id))


@router.post("/{trip_id}/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
def record_settlement(trip_id: int, data: SettlementCreate, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user), today: date = Depends(get_today)):
    return svc.settlement_out(svc.add_settlement(db, _trip(db, user, trip_id), data, today))


@router.get("/{trip_id}/settlements", response_model=list[SettlementOut])
def list_settlements(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [svc.settlement_out(s) for s in _trip(db, user, trip_id).settlements]


@router.delete("/{trip_id}/settlements/{settlement_id}", status_code=NO_CONTENT)
def delete_settlement(trip_id: int, settlement_id: int, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    db.delete(_child(_trip(db, user, trip_id).settlements, settlement_id, "Settlement"))
    db.commit()
    return Response(status_code=NO_CONTENT)
