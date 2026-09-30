"""
app/reports/pdf.py — PDF report generation with ReportLab.
"""

from __future__ import annotations
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def generate_scan_pdf(scan_result: dict) -> bytes:
    """Generate a PDF report for a single scan result dict."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="MedSure Vision Screening Report")
        styles = getSampleStyleSheet()
        story = []

        # Header
        story.append(Paragraph("MedSure Vision — Screening Report", styles["Title"]))
        story.append(Paragraph("<i>Screening only. This does not confirm authenticity.</i>", styles["Italic"]))
        story.append(Spacer(1, 6 * mm))

        # Meta
        label = scan_result.get("label", "unknown")
        ts = scan_result.get("ts", "")
        story.append(Paragraph(f"<b>Result:</b> {label.upper().replace('_', ' ')}", styles["Heading2"]))
        story.append(Paragraph(f"<b>Scan ID:</b> {scan_result.get('id', '')}", styles["Normal"]))
        story.append(Paragraph(f"<b>Timestamp:</b> {ts}", styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

        # Field table
        ocr = scan_result.get("ocr") or {}
        code = scan_result.get("code") or {}
        field_data = [["Field", "Printed (OCR)", "Code Value"]]
        for field_name in ("name", "batch", "expiry", "manufacturer", "strength", "form"):
            ocr_field = ocr.get(field_name) or {}
            code_val = code.get(field_name) if field_name in ("batch", "expiry", "gtin") else "-"
            field_data.append([
                field_name.capitalize(),
                str(ocr_field.get("value", "-") or "-"),
                str(code_val or "-"),
            ])

        t = Table(field_data, colWidths=[40 * mm, 75 * mm, 75 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#635BFF")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FC")]),
        ]))
        story.append(Paragraph("<b>Field Cross-Check</b>", styles["Heading3"]))
        story.append(t)
        story.append(Spacer(1, 4 * mm))

        # Reasons
        reasons = scan_result.get("reasons", [])
        if reasons:
            story.append(Paragraph("<b>Reasons for this result</b>", styles["Heading3"]))
            for r in reasons:
                story.append(Paragraph(f"• [{r.get('severity', '').upper()}] {r.get('text', '')}", styles["Normal"]))
            story.append(Spacer(1, 4 * mm))

        # Checked / not checked
        checked = scan_result.get("checked", [])
        not_checked = scan_result.get("not_checked", [])
        story.append(Paragraph("<b>Inspection Coverage</b>", styles["Heading3"]))
        story.append(Paragraph("Checked:", styles["Heading4"]))
        for c in checked:
            story.append(Paragraph(f"✓ {c}", styles["Normal"]))
        story.append(Paragraph("Not checked:", styles["Heading4"]))
        for nc in not_checked:
            story.append(Paragraph(f"✗ {nc}", styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

        # Next steps
        next_steps = scan_result.get("next_steps", [])
        if next_steps:
            story.append(Paragraph("<b>Next Steps</b>", styles["Heading3"]))
            for i, step in enumerate(next_steps, 1):
                story.append(Paragraph(f"{i}. {step}", styles["Normal"]))

        # Simulated notice
        sim_flags = scan_result.get("simulated_flags", [])
        if sim_flags:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(
                f"<b>Note:</b> This result includes simulated data: {', '.join(sim_flags)}. "
                "Do not use for regulatory purposes.",
                styles["Italic"]
            ))

        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(
            "Screening only. This does not confirm authenticity. "
            "Always verify with your supplier and regulatory authorities for suspected packs.",
            styles["Italic"]
        ))

        doc.build(story)
        return buf.getvalue()

    except ImportError:
        logger.error("pdf: reportlab not installed")
        return b"%PDF placeholder — reportlab not installed"
    except Exception as exc:
        logger.error("pdf: generation error: %s", exc)
        return b"%PDF error during generation"


def generate_session_pdf(session, flagged_scans) -> bytes:
    """Generate PDF for a receiving session's flagged pack list."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="MedSure Receiving Session Report")
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("MedSure Vision — Receiving Session Report", styles["Title"]))
        story.append(Paragraph(f"Supplier: {session.supplier or 'N/A'}", styles["Normal"]))
        story.append(Paragraph(f"Session: {session.id}", styles["Normal"]))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"Flagged packs: {len(flagged_scans)}", styles["Heading2"]))

        if flagged_scans:
            data = [["Pack ID", "Name", "Batch", "Expiry", "Label", "Reason"]]
            for s in flagged_scans:
                data.append([
                    s.id[:8] + "...",
                    (s.name or "")[:30],
                    s.batch or "",
                    s.expiry or "",
                    s.label.upper().replace("_", " "),
                    (s.top_reason or "")[:50],
                ])
            t = Table(data, colWidths=[25 * mm, 35 * mm, 25 * mm, 20 * mm, 30 * mm, 55 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#635BFF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]))
            story.append(t)

        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Screening only. This does not confirm authenticity.", styles["Italic"]))

        doc.build(story)
        return buf.getvalue()

    except Exception as exc:
        logger.error("pdf: session pdf error: %s", exc)
        return b"%PDF error"
