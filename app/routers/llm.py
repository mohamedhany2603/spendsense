from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import LlmCostLog, User
from ..schemas import CategorizeRequest, CategorizeResponse, CostLogOut, CostSummary
from ..services.categorizer import classify_merchant

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.post("/categorize", response_model=CategorizeResponse)
def categorize(
    payload: CategorizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CategorizeResponse:
    """One narrow AI job behind an endpoint — merchant to category, validated."""
    result = classify_merchant(db, payload.merchant, payload.description)
    return CategorizeResponse(
        merchant=result.merchant,
        category=result.category_name,
        category_id=result.category_id,
        source=result.source,
        cost_estimated_usd=round(result.cost_estimated_usd, 8),
    )


@router.get("/costs", response_model=CostSummary)
def cost_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CostSummary:
    logs = (
        db.query(LlmCostLog)
        .order_by(LlmCostLog.created_at.desc())
        .limit(200)
        .all()
    )
    return CostSummary(
        total_calls=len(logs),
        successful_calls=sum(1 for l in logs if l.success),
        failed_calls=sum(1 for l in logs if not l.success),
        total_estimated_cost_usd=round(sum(l.estimated_cost_usd for l in logs), 8),
        logs=[CostLogOut.model_validate(l) for l in logs],
    )