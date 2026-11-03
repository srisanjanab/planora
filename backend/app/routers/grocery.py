from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.grocery import GroceryItem
from app.models.user import User
from app.schemas.grocery import (
    ClearResult,
    GroceryCategory,
    GroceryCreate,
    GroceryOut,
    GrocerySummary,
    GroceryUpdate,
)
from app.services import grocery as svc

router = APIRouter(prefix="/grocery", tags=["grocery"])


def _get_item(db: Session, user: User, item_id: int) -> GroceryItem:
    item = db.scalar(select(GroceryItem).where(GroceryItem.id == item_id, GroceryItem.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items", response_model=list[GroceryOut])
def list_items(
    bought: bool | None = None,
    category: GroceryCategory | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(GroceryItem).where(GroceryItem.user_id == user.id)
    if not include_archived:
        query = query.where(GroceryItem.is_archived.is_(False))
    if bought is not None:
        query = query.where(GroceryItem.is_bought.is_(bought))
    if category:
        query = query.where(GroceryItem.category == category.value)
    return db.scalars(query.order_by(GroceryItem.is_bought, GroceryItem.category, GroceryItem.name)).all()


@router.post("/items", response_model=GroceryOut, status_code=status.HTTP_201_CREATED)
def add_item(data: GroceryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = GroceryItem(
        user_id=user.id,
        name=data.name.strip(),
        category=data.category.value,
        quantity=data.quantity.strip(),
        estimated_price=data.estimated_price,
        priority=data.priority.value,
        notes=data.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/summary", response_model=GrocerySummary)
def grocery_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.build_summary(db, user.id)


@router.post("/clear-completed", response_model=ClearResult)
def clear_completed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Archives every bought item (hidden from the list, kept in the database)."""
    return ClearResult(archived=svc.archive_completed(db, user.id))


@router.patch("/items/{item_id}", response_model=GroceryOut)
def update_item(
    item_id: int,
    data: GroceryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = _get_item(db, user, item_id)
    changes = data.model_dump(exclude_unset=True)
    if "is_bought" in changes and changes["is_bought"] is not None:
        svc.set_bought(item, changes.pop("is_bought"))
    changes.pop("is_bought", None)
    for field, value in changes.items():
        if field in ("category", "priority") and value is not None:
            value = value.value
        if field in ("name", "category", "quantity", "priority") and value is None:
            continue
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_get_item(db, user, item_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
