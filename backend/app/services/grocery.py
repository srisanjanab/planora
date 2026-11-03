from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.grocery import GroceryItem
from app.schemas.grocery import GrocerySummary

ZERO = Decimal("0.00")


def set_bought(item: GroceryItem, is_bought: bool) -> None:
    """The checkbox. Ticking records when; unticking (accidental tick) clears it."""
    if is_bought and not item.is_bought:
        item.bought_at = datetime.now(timezone.utc)
    if not is_bought:
        item.bought_at = None
    item.is_bought = is_bought


def build_summary(db: Session, user_id: int) -> GrocerySummary:
    active = (GroceryItem.user_id == user_id, GroceryItem.is_archived.is_(False))
    remaining = db.scalar(select(func.count(GroceryItem.id)).where(*active, GroceryItem.is_bought.is_(False)))
    bought = db.scalar(select(func.count(GroceryItem.id)).where(*active, GroceryItem.is_bought.is_(True)))
    cost = db.scalar(
        select(func.coalesce(func.sum(GroceryItem.estimated_price), 0)).where(
            *active, GroceryItem.is_bought.is_(False)
        )
    )
    return GrocerySummary(
        remaining=remaining or 0,
        bought=bought or 0,
        estimated_remaining_cost=Decimal(cost).quantize(ZERO),
    )


def archive_completed(db: Session, user_id: int) -> int:
    result = db.execute(
        update(GroceryItem)
        .where(
            GroceryItem.user_id == user_id,
            GroceryItem.is_bought.is_(True),
            GroceryItem.is_archived.is_(False),
        )
        .values(is_archived=True)
    )
    db.commit()
    return result.rowcount or 0
