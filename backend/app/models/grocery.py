from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GroceryItem(Base):
    __tablename__ = "grocery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20), default="OTHER")
    quantity: Mapped[str] = mapped_column(String(50), default="1")  # free text: "2 kg", "1 packet"
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="MEDIUM")
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_bought: Mapped[bool] = mapped_column(Boolean, default=False)
    bought_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)  # "Clear completed" archives, never hard-deletes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
