from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, bills

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


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
