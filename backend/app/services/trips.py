from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.trip import (
    ItineraryItem, Settlement, Ticket, Trip, TripExpense, TripExpenseShare, TripMember,
)
from app.models.user import User
from app.schemas.trip import (
    BalanceRow, ItineraryCreate, MemberOut, SettlementCreate, SettlementOut, SettlementReport,
    ShareOut, SplitType, SuggestedPayment, TicketCreate, TripCreate, TripExpenseCreate,
    TripExpenseOut, TripOut, TripSummary, TripUpdate,
)
from app.services import splits as sp

ZERO = Decimal("0.00")


def bad(msg: str, code: int = 400):
    raise HTTPException(status_code=code, detail=msg)


# ---------- trips ----------

def trip_status(t: Trip, today: date) -> str:
    if today > t.end_date:
        return "PAST"
    return "UPCOMING" if today < t.start_date else "ONGOING"


def summary(t: Trip, today: date) -> TripSummary:
    return TripSummary(
        id=t.id, name=t.name, destination=t.destination, start_date=t.start_date, end_date=t.end_date,
        status=trip_status(t, today), budget=t.budget,
        total_spent=sum((e.amount for e in t.expenses), ZERO), member_count=len(t.members),
    )


def trip_out(t: Trip, today: date) -> TripOut:
    return TripOut(
        **summary(t, today).model_dump(), description=t.description,
        members=[MemberOut.model_validate(m) for m in t.members],
    )


def _clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        bad("Member name cannot be empty")
    return name


def _ensure_new_name(t: Trip, name: str) -> None:
    if any(m.display_name.lower() == name.lower() for m in t.members):
        bad(f"'{name}' is already on this trip. Use a different name (e.g. add a surname).")


def create_trip(db: Session, user: User, data: TripCreate) -> Trip:
    t = Trip(
        owner_id=user.id, name=data.name.strip(), destination=data.destination.strip(),
        start_date=data.start_date, end_date=data.end_date, budget=data.budget, description=data.description,
    )
    db.add(t)
    db.flush()
    db.add(TripMember(trip_id=t.id, display_name=_clean_name(user.name), user_id=user.id))
    db.flush()
    db.refresh(t)
    for raw in data.member_names:
        name = _clean_name(raw)
        _ensure_new_name(t, name)
        db.add(TripMember(trip_id=t.id, display_name=name))
        db.flush()
        db.refresh(t)
    db.commit()
    db.refresh(t)
    return t


def update_trip(db: Session, t: Trip, data: TripUpdate) -> Trip:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field in ("name", "start_date", "end_date") and value is None:
            continue
        setattr(t, field, value)
    if t.end_date < t.start_date:
        db.rollback()
        bad("end_date cannot be before start_date")
    db.commit()
    db.refresh(t)
    return t


def get_member(t: Trip, member_id: int) -> TripMember:
    for m in t.members:
        if m.id == member_id:
            return m
    bad(f"Member {member_id} is not on this trip")


def add_member(db: Session, t: Trip, display_name: str) -> TripMember:
    name = _clean_name(display_name)
    _ensure_new_name(t, name)
    m = TripMember(trip_id=t.id, display_name=name)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def remove_member(db: Session, t: Trip, member_id: int) -> None:
    m = get_member(t, member_id)
    used = (
        any(e.paid_by_member_id == m.id or any(s.member_id == m.id for s in e.shares) for e in t.expenses)
        or any(m.id in (s.from_member_id, s.to_member_id) for s in t.settlements)
    )
    if m.user_id == t.owner_id:
        bad("You cannot remove yourself from your own trip", 409)
    if used:
        bad("This person already appears in expenses or settlements. Delete those first.", 409)
    db.delete(m)
    db.commit()


# ---------- itinerary & tickets ----------

def add_itinerary(db: Session, t: Trip, data: ItineraryCreate) -> ItineraryItem:
    if not t.start_date <= data.day <= t.end_date:
        bad(f"Day must be within the trip dates ({t.start_date} to {t.end_date})")
    item = ItineraryItem(trip_id=t.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def add_ticket(db: Session, t: Trip, data: TicketCreate) -> Ticket:
    ticket = Ticket(trip_id=t.id, **{**data.model_dump(), "type": data.type.value})
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


# ---------- expenses & splits ----------

def add_expense(db: Session, t: Trip, data: TripExpenseCreate, today: date) -> TripExpense:
    members = {m.id for m in t.members}
    if data.paid_by_member_id not in members:
        bad(f"Member {data.paid_by_member_id} is not on this trip")
    total = sp.to_paise(data.amount)

    if data.split_type == SplitType.EQUAL:
        if data.shares:
            bad("'shares' is only used with split_type CUSTOM")
        ids = data.participant_ids if data.participant_ids is not None else sorted(members)
        if not ids:
            bad("Choose at least one person to share this expense")
        if len(set(ids)) != len(ids) or not set(ids) <= members:
            bad("participant_ids must be unique members of this trip")
        shares = sp.equal_shares(total, ids)
    else:
        if not data.shares:
            bad("CUSTOM split needs 'shares' with an amount for each person")
        ids = [s.member_id for s in data.shares]
        if len(set(ids)) != len(ids) or not set(ids) <= members:
            bad("shares must list each trip member at most once")
        shares = {s.member_id: sp.to_paise(s.amount) for s in data.shares}
        if sum(shares.values()) != total:
            bad(f"Shares add up to {sp.from_paise(sum(shares.values()))} but the expense is {data.amount}")

    exp = TripExpense(
        trip_id=t.id, title=data.title.strip(), category=data.category.value, amount=data.amount,
        paid_by_member_id=data.paid_by_member_id, spent_on=data.spent_on or today,
        split_type=data.split_type.value,
        shares=[TripExpenseShare(member_id=m, share_amount=sp.from_paise(p)) for m, p in sorted(shares.items())],
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def expense_out(e: TripExpense) -> TripExpenseOut:
    return TripExpenseOut(
        id=e.id, title=e.title, category=e.category, amount=e.amount, paid_by_member_id=e.paid_by_member_id,
        paid_by_name=e.paid_by.display_name, spent_on=e.spent_on, split_type=e.split_type,
        shares=[ShareOut(member_id=s.member_id, member_name=s.member.display_name, share_amount=s.share_amount)
                for s in e.shares],
    )


# ---------- balances & settlements ----------

def settlement_report(t: Trip) -> SettlementReport:
    ids = [m.id for m in t.members]
    paid, share, sent, recv = ({i: 0 for i in ids} for _ in range(4))
    for e in t.expenses:
        paid[e.paid_by_member_id] += sp.to_paise(e.amount)
        for s in e.shares:
            share[s.member_id] += sp.to_paise(s.share_amount)
    for s in t.settlements:
        sent[s.from_member_id] += sp.to_paise(s.amount)
        recv[s.to_member_id] += sp.to_paise(s.amount)
    # Who is owed money: paid more than their share, adjusted by paybacks already made.
    balance = {i: paid[i] - share[i] + sent[i] - recv[i] for i in ids}
    names = {m.id: m.display_name for m in t.members}
    return SettlementReport(
        total_spent=sp.from_paise(sum(paid.values())),
        balances=[
            BalanceRow(
                member_id=i, name=names[i], paid=sp.from_paise(paid[i]), share=sp.from_paise(share[i]),
                settlements_sent=sp.from_paise(sent[i]), settlements_received=sp.from_paise(recv[i]),
                balance=sp.from_paise(balance[i]),
            ) for i in ids
        ],
        suggested_payments=[
            SuggestedPayment(from_member_id=d, from_name=names[d], to_member_id=c, to_name=names[c],
                             amount=sp.from_paise(p))
            for d, c, p in sp.suggest_settlements(balance)
        ],
    )


def add_settlement(db: Session, t: Trip, data: SettlementCreate, today: date) -> Settlement:
    if data.from_member_id == data.to_member_id:
        bad("A person cannot pay themselves")
    get_member(t, data.from_member_id)
    get_member(t, data.to_member_id)
    st = Settlement(
        trip_id=t.id, from_member_id=data.from_member_id, to_member_id=data.to_member_id,
        amount=data.amount, settled_on=data.settled_on or today,
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return st


def settlement_out(s: Settlement) -> SettlementOut:
    return SettlementOut(
        id=s.id, from_member_id=s.from_member_id, from_name=s.from_member.display_name,
        to_member_id=s.to_member_id, to_name=s.to_member.display_name, amount=s.amount, settled_on=s.settled_on,
    )
