"""Reporting — monthly PDF generation (ReportLab).

Builds a readable one-page-ish PDF summary: total spend, per-category breakdown
and the top merchants for a given month. Files are written under ./reports which
is gitignored; a database row tracks each generated report for download endpoints.
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..models import Report, Transaction, TransactionStatus

REPORTS_DIR = Path("reports")


def _month_range(month: str) -> tuple[str, str]:
    """Return (start, end) datetimes for a YYYY-MM month."""
    start = datetime.strptime(month, "%Y-%m")
    end_month = 12 if start.month == 12 else start.month + 1
    end_year = start.year + 1 if start.month == 12 else start.year
    stop = datetime(end_year, end_month, 1)
    return start.isoformat(), stop.isoformat()


def _summarize(db: Session, user_id: int, month: str) -> tuple[list[tuple], list[tuple], float, int]:
    start, stop = _month_range(month)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.categorized,
            Transaction.created_at >= start,
            Transaction.created_at < stop,
        )
        .all()
    )
    total = sum(t.amount for t in rows if t.amount > 0)

    by_category: dict[str, float] = {}
    merchant_totals: dict[str, float] = {}
    for t in rows:
        name = t.category.name if t.category else "Uncategorized"
        by_category[name] = by_category.get(name, 0.0) + t.amount
        merchant_totals[t.merchant] = merchant_totals.get(t.merchant, 0.0) + t.amount

    category_rows = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    category_rows = [(name, f"{amount:.2f}") for name, amount in category_rows]
    top_merchants = sorted(merchant_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_merchants = [(name, f"{amount:.2f}") for name, amount in top_merchants]
    return category_rows, top_merchants, total, len(rows)


def generate_report_pdf(db: Session, user_id: int, month: str, user_name: str) -> Report:
    """Generate a PDF report for a month and persist a Report row."""
    REPORTS_DIR.mkdir(exist_ok=True)

    category_rows, merchant_rows, total, count = _summarize(db, user_id, month)

    file_name = f"spendsense-report-{user_id}-{month}.pdf"
    path = REPORTS_DIR / file_name

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            title=f"SpendSense report — {month}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>SpendSense — Monthly Report</b>", styles["Title"]),
        Paragraph(f"Month: {month} &nbsp;|&nbsp; User: {user_name}", styles["Normal"]),
        Paragraph(f"Total spending: <b>${total:.2f}</b> across {count} transactions",
                  styles["Heading2"]),
        Spacer(1, 12),
        Paragraph("Spending by category", styles["Heading3"]),
    ]

    def _table(headers: list[str], rows: list[list[str]]) -> None:
        data = [headers] + rows
        t = Table(data)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243b53")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    _table(["Category", "Amount (USD)"], category_rows or [["—", "—"]])
    story.append(Paragraph("Top merchants", styles["Heading3"]))
    _table(["Merchant", "Amount (USD)"], merchant_rows or [["—", "—"]])

    doc.build(story)

    report = Report(
        user_id=user_id, month=month, file_name=file_name,
        total_expense=round(total, 2), transaction_count=count,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def report_abs_path(report: Report) -> Path:
    return REPORTS_DIR / report.file_name


def category_totals_for_month(db: Session, user_id: int, month: str) -> dict[str, dict]:
    """Raw per-category aggregates used by the analytics endpoint."""
    start, stop = _month_range(month)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.categorized,
            Transaction.created_at >= start,
            Transaction.created_at < stop,
        )
        .all()
    )
    result: dict[str, dict] = {}
    for t in rows:
        name = t.category.name if t.category else "Uncategorized"
        entry = result.setdefault(name, {"total": 0.0, "count": 0})
        entry["total"] += t.amount
        entry["count"] += 1
    return {k: {"total": round(v["total"], 2), "count": v["count"]} for k, v in result.items()}