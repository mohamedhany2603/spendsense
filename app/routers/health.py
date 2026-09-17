from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import User
from ..services import scheduler as scheduler_mod

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    active = scheduler_mod._scheduler
    return {
        "status": "ok",
        "database": "ok",
        "scheduler": active is not None,
        "jobs": [job.id for job in active.get_jobs()] if active else [],
    }


@router.get("/health/me")
def health_auth(current_user: User = Depends(get_current_user)) -> dict:
    return {"status": "ok", "authenticated_as": current_user.email}