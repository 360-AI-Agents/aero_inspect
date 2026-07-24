import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from backend.repositories.inspection_repository import InspectionRepository
from backend.repositories.violation_repository import ViolationRepository
from backend.repositories.report_repository import ReportRepository
from backend.utils.helpers import generate_report_title
from backend.utils.calculations import build_violation_breakdown

REPORTS_DIR = "backend/uploads/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

NAVY = colors.HexColor("#12294d")
LIGHT_BG = colors.HexColor("#f3f6fa")
IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist(dt: datetime) -> datetime:
    """Converts a naive/UTC datetime to IST for display purposes."""
    if dt is None:
        return None
    return dt + IST_OFFSET


class ReportService:

    @staticmethod
    def generate_report(db: Session, inspection_id: int):
        inspection = InspectionRepository.get_by_id(db, inspection_id)
        if not inspection:
            return None

        violations = ViolationRepository.get_by_inspection(db, inspection_id)
        breakdown = build_violation_breakdown(violations)

        summary = (
            f"Inspection '{inspection.inspection_name}' recorded "
            f"{inspection.workers_detected} workers with "
            f"{inspection.total_violations} total violations. "
            f"Compliance score: {inspection.compliance_score}%. "
            f"Status: {inspection.inspection_status}."
        )

        report_title = generate_report_title(inspection.inspection_name)

        report = ReportRepository.create(
            db,
            inspection_id=inspection_id,
            report_title=report_title,
            summary=summary
        )

        return {
            "report_id": report.id,
            "report_title": report.report_title,
            "summary": report.summary,
            "violation_breakdown": breakdown,
            "generated_at": report.generated_at
        }

    @staticmethod
    def generate_pdf(db: Session, inspection_id: int):
        inspection = InspectionRepository.get_by_id(db, inspection_id)
        if not inspection:
            return None

        violations = ViolationRepository.get_by_inspection(db, inspection_id)
        breakdown = build_violation_breakdown(violations)

        filename = f"report_{inspection_id}_{int(datetime.utcnow().timestamp())}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=0.8*inch, bottomMargin=0.8*inch)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=20,
                                      textColor=NAVY, spaceAfter=10, leading=24)
        sub_style = ParagraphStyle("Sub", fontName="Helvetica", fontSize=10,
                                    textColor=colors.HexColor("#666666"), spaceAfter=26)
        h_style = ParagraphStyle("H", fontName="Helvetica-Bold", fontSize=12,
                                  textColor=NAVY, spaceBefore=16, spaceAfter=8)
        body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=14)
        cell_style = ParagraphStyle("Cell", fontName="Helvetica", fontSize=9, leading=12)
        cell_header_style = ParagraphStyle("CellHeader", fontName="Helvetica-Bold", fontSize=9,
                                            leading=12, textColor=colors.white)

        generated_ist = to_ist(datetime.utcnow())
        recorded_ist = to_ist(inspection.created_at)

        story = []
        story.append(Paragraph("AeroInspect AI — Inspection Report", title_style))
        story.append(Paragraph(
            f"Generated {generated_ist.strftime('%d %B %Y, %H:%M')} IST", sub_style
        ))

        story.append(Paragraph("Inspection Summary", h_style))
        summary_data = [
            ["Inspection Name", inspection.inspection_name],
            ["Workers Detected", str(inspection.workers_detected)],
            ["Total Violations", str(inspection.total_violations)],
            ["Compliance Score", f"{inspection.compliance_score}%"],
            ["Status", inspection.inspection_status],
            ["Recorded", f"{recorded_ist.strftime('%d %b %Y, %H:%M')} IST"],
        ]
        summary_table = Table(
            [[Paragraph(f"<b>{k}</b>", body_style), Paragraph(str(v), body_style)] for k, v in summary_data],
            colWidths=[2.0*inch, 3.5*inch]
        )
        summary_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cccccc")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)

        story.append(Paragraph("Violation Breakdown", h_style))
        breakdown_data = [[Paragraph("Category", cell_header_style), Paragraph("Count", cell_header_style)]]
        for cat, count in breakdown.items():
            breakdown_data.append([
                Paragraph(cat.replace("_", " ").title(), cell_style),
                Paragraph(str(count), cell_style)
            ])
        breakdown_table = Table(breakdown_data, colWidths=[3.5*inch, 2.0*inch])
        breakdown_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(breakdown_table)

        if violations:
            story.append(Paragraph("Individual Violations", h_style))
            v_data = [[
                Paragraph("Violation", cell_header_style),
                Paragraph("Category", cell_header_style),
                Paragraph("Severity", cell_header_style),
                Paragraph("Count", cell_header_style),
                Paragraph("Time (IST)", cell_header_style),
            ]]
            for v in violations:
                v_time_ist = to_ist(v.created_at)
                v_data.append([
                    Paragraph(v.violation_name, cell_style),
                    Paragraph(v.category.replace("_", " ").title(), cell_style),
                    Paragraph(v.severity.title(), cell_style),
                    Paragraph(str(v.count), cell_style),
                    Paragraph(v_time_ist.strftime("%d %b, %H:%M"), cell_style),
                ])
            v_table = Table(v_data, colWidths=[2.0*inch, 1.1*inch, 0.9*inch, 0.6*inch, 1.0*inch])
            v_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(v_table)

        story.append(Spacer(1, 20))
        story.append(Paragraph(
            "This report was generated automatically by AeroInspect AI based on live "
            "site monitoring data.", sub_style
        ))

        doc.build(story)
        return filepath