from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Report, User
from ..schemas import ReportGenerateRequest, ReportOut
from ..services.reports import generate_report_pdf, report_abs_path

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_report(
    payload: ReportGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    return generate_report_pdf(db, current_user.id, payload.month, current_user.name)


@router.get("", response_model=list[ReportOut])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.user_id == current_user.id)
        .order_by(Report.month.desc(), Report.generated_at.desc())
        .all()
    )


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    report = (
        db.query(Report)
        .filter(Report.id == report_id, Report.user_id == current_user.id)
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    path = report_abs_path(report)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file missing on disk")
    return FileResponse(path, media_type="application/pdf",
                        filename=report.file_name)