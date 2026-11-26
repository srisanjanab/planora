from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, bills, dashboard, expenses, grocery, insights, trips

app = FastAPI(title="Planora API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bills.bills_router)
app.include_router(bills.occurrences_router)
app.include_router(expenses.router)
app.include_router(grocery.router)
app.include_router(trips.router)
app.include_router(insights.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
