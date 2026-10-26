from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BillTemplate(Base):
    """The recurring definition, e.g. 'Internet, 999, monthly, due on the 10th'."""

    __tablename__ = "bill_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(30), default="OTHER")
    default_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_variable: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(String(10), default="MONTHLY")
    first_due_date: Mapped[date] = mapped_column(Date)  # its day-of-month is the anchor for every cycle
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=3)
    auto_create_next: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    occurrences: Mapped[list["BillOccurrence"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="BillOccurrence.due_date",
    )


class BillOccurrence(Base):
    """One cycle of a bill, e.g. 'Internet, October 2026'. Stored status is PENDING / PAID / SKIPPED.
    DUE / OVERDUE / UPCOMING are computed from today's date, never stored."""

    __tablename__ = "bill_occurrences"
    __table_args__ = (UniqueConstraint("template_id", "due_date", name="uq_occurrence_template_due"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("bill_templates.id", ondelete="CASCADE"), index=True)
    due_date: Mapped[date] = mapped_column(Date)
    reminder_date: Mapped[date] = mapped_column(Date)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    template: Mapped["BillTemplate"] = relationship(back_populates="occurrences")
    payment: Mapped["BillPayment | None"] = relationship(
        back_populates="occurrence", uselist=False, cascade="all, delete-orphan"
    )


class BillPayment(Base):
    __tablename__ = "bill_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("bill_occurrences.id", ondelete="CASCADE"), unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_on: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    occurrence: Mapped["BillOccurrence"] = relationship(back_populates="payment")
