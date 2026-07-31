"""Application entry point.

Single job: wire the app together — lifespan, routes, static files.

FastAPI serves the frontend itself, so the whole project is one process and one
command (`uvicorn app.main:app`). That also means the browser and the API share
an origin, so CORS never comes up — roughly twenty minutes better spent on the
product (PLAN.md decision #3).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.db import init_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rebuilt from backend/seed/*.json on every boot, so a reviewer restarting
    # the server always sees exactly the state the README describes.
    init_db(rebuild=True)
    yield


app = FastAPI(
    title="LAAM — Purchase Confidence API",
    description=(
        "A small slice of a product-discovery experience: per-size availability, "
        "a true price breakdown, an honest delivery window, and constraint-filtered "
        "alternatives when a check fails.\n\n"
        "Every query parameter on `/confidence` is optional by design — the endpoint "
        "answers correctly when it knows nothing about the customer, which is the "
        "state every first-time visitor is in."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted last: the API router above takes precedence, this catches everything
# else and serves the two static pages.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
