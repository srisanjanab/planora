# Import every model here so Alembic can see them.
from app.models.user import User  # noqa: F401
from app.models.bill import BillOccurrence, BillPayment, BillTemplate  # noqa: F401
