import datetime as dt
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120), default="")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    members: Mapped[list["TripMember"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripMember.id"
    )
    itinerary: Mapped[list["ItineraryItem"]] = relationship(
        cascade="all, delete-orphan", order_by="ItineraryItem.day, ItineraryItem.time, ItineraryItem.id"
    )
    tickets: Mapped[list["Ticket"]] = relationship(cascade="all, delete-orphan", order_by="Ticket.id")
    expenses: Mapped[list["TripExpense"]] = relationship(cascade="all, delete-orphan")
    settlements: Mapped[list["Settlement"]] = relationship(cascade="all, delete-orphan")


class TripMember(Base):
    """A person on the trip. They do not need an account: just a display name."""

    __tablename__ = "trip_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="members")


class ItineraryItem(Base):
    __tablename__ = "trip_itinerary"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    title: Mapped[str] = mapped_column(String(150))
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Ticket(Base):
    """Flight / train / bus / event tickets and hotel bookings."""

    __tablename__ = "trip_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10), default="OTHER")
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TripExpense(Base):
    __tablename__ = "trip_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(20), default="OTHER")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_by_member_id: Mapped[int] = mapped_column(ForeignKey("trip_members.id"))
    spent_on: Mapped[date] = mapped_column(Date)
    split_type: Mapped[str] = mapped_column(String(10), default="EQUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    paid_by: Mapped["TripMember"] = relationship(foreign_keys=[paid_by_member_id])
    shares: Mapped[list["TripExpenseShare"]] = relationship(
        cascade="all, delete-orphan", order_by="TripExpenseShare.member_id"
    )


class TripExpenseShare(Base):
    __tablename__ = "trip_expense_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("trip_expenses.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("trip_members.id"))
    share_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    member: Mapped["TripMember"] = relationship()


class Settlement(Base):
    """A real payback: from_member handed `amount` to to_member."""

    __tablename__ = "trip_settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    from_member_id: Mapped[int] = mapped_column(ForeignKey("trip_members.id"))
    to_member_id: Mapped[int] = mapped_column(ForeignKey("trip_members.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    settled_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    from_member: Mapped["TripMember"] = relationship(foreign_keys=[from_member_id])
    to_member: Mapped["TripMember"] = relationship(foreign_keys=[to_member_id])
