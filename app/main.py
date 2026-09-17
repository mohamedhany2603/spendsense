"""SpendSense — LLM-powered expense tracker.

App entrypoint. FastAPI lifespan creates the schema and starts the background
scheduler (cron jobs) when ENABLE_SCHEDULER is true.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import analytics, auth, health, llm, reports, transactions
from .services.categorizer import ensure_default_categories
from .services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("spendsense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_default_categories(db)
    if get_settings().enable_scheduler:
        start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="SpendSense API",
    description="LLM-powered personal expense tracker. Categorize transactions, "
                "see monthly analytics, get a PDF report — the boring part done for you.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(llm.router)
app.include_router(reports.router)