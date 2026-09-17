from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import get_current_user, get_db
from ..models import User
from ..schemas import CategoryTotal, MonthlyAnalytics
from ..services.cache import get_cached_analytics, set_cached_analytics
from ..services.reports import category_totals_for_month

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/monthly", response_model=MonthlyAnalytics)
def monthly_analytics(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonthlyAnalytics:
    """Expensive aggregate — cached with a TTL. Cache is invalidated on writes."""
    settings = get_settings()

    cached = get_cached_analytics(current_user.id, month, settings.cache_ttl_seconds)
    if cached is not None:
        return MonthlyAnalytics(**cached, cached=True)

    totals = category_totals_for_month(db, current_user.id, month)
    payload = MonthlyAnalytics(
        month=month,
        total_expense=round(sum(c["total"] for c in totals.values()), 2),
        total_transactions=sum(c["count"] for c in totals.values()),
        by_category=[
            CategoryTotal(category=name, total=round(v["total"], 2), count=v["count"])
            for name, v in totals.items()
        ],
        cached=False,
    ).model_dump()
    payload.pop("cached")  # cached is a read-time flag, not stored data

    set_cached_analytics(current_user.id, month, payload, settings.cache_ttl_seconds)
    return MonthlyAnalytics(**payload, cached=False)