from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, get_today
from app.models.user import User
from app.schemas.insights import InsightsOut
from app.services.insights import build_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsOut)
def insights(db: Session = Depends(get_db), user: User = Depends(get_current_user), today: date = Depends(get_today)):
    return build_insights(db, user.id, today)
