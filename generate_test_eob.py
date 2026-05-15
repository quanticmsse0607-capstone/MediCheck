#!/usr/bin/env python3
"""
Generate a sample EOB (Explanation of Benefits) PDF for testing MediCheck.
Matches test_bill.pdf exactly.

Designed to trigger exactly 3 meaningful errors:
  Module 2 — Medicare Rate Outlier: CPT 99282 ($850 vs $47 Medicare = 1809%)
  Module 3 — EOB Reconciliation:    CPT 99291 bill=$1200 vs EOB=$800 ($400 mismatch)
  Module 4 — No Surprises Act:      CPT 99215 marked OON (out-of-network)

The Billed column matches the provider bill EXCEPT for CPT 99291 which is
intentionally different to trigger Module 3.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import os


def create_sample_eob():
    output_dir = os.path.join(os.path.dirname(__file__), "test-data", "synthetic")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "test_eob.pdf")

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # ── Styles ──────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#006633"),
        spaceAfter=20,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#006633"),
        spaceAfter=10,
        spaceBefore=12,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#CC0000"),
        spaceAfter=4,
    )

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("EXPLANATION OF BENEFITS", title_style))
    story.append(
        Paragraph("This is not a bill. Keep for your records.", styles["Normal"])
    )
    story.append(Spacer(1, 0.2 * inch))

    # ── Insurer info ─────────────────────────────────────────────────────────
    insurer_data = [
        ["UnitedHealthcare PPO Gold", "EOB Date: 04/20/2026"],
        ["P.O. Box 740800", "Claim #: UHC-2026-789456"],
        ["Atlanta, GA 30374", "Group #: EMP-2024-001"],
        ["Member Services: 1-800-555-0199", ""],
    ]
    insurer_table = Table(insurer_data, colWidths=[3.5 * inch, 3 * inch])
    insurer_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(insurer_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Member info ──────────────────────────────────────────────────────────
    story.append(Paragraph("MEMBER INFORMATION", heading_style))
    member_data = [
        ["Member Name:", "John Michael Thompson", "Member ID:", "MH-789456123"],
        ["Date of Birth:", "06/15/1975", "Plan:", "PPO Gold"],
        ["Provider:", "Metropolitan Hospital Center", "NPI:", "1234567890"],
        ["Service Period:", "04/05/2026 - 04/08/2026", "Copay:", "$50.00"],
    ]
    member_table = Table(
        member_data, colWidths=[1.5 * inch, 2.2 * inch, 1.5 * inch, 2.3 * inch]
    )
    member_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E6F4EA")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E6F4EA")),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ]
        )
    )
    story.append(member_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Benefits detail ──────────────────────────────────────────────────────
    story.append(Paragraph("BENEFITS DETAIL", heading_style))

    # IMPORTANT: Billed column = same as provider bill EXCEPT CPT 99291
    # CPT 99291: provider bill = $1,200 but EOB billed = $800 → triggers Module 3
    # CPT 99215: marked OON → triggers Module 4 No Surprises Act
    service_data = [
        ["Date", "CPT", "Billed", "Discount", "Plan Paid", "Your Cost", "Network"],
        # ── In-network charges ────────────────────────────────────────────────
        ["04/05/2026", "99282", "$850.00", "$637.50", "$170.00", "$42.50", "IN"],
        ["04/05/2026", "71020", "$425.00", "$255.00", "$136.00", "$34.00", "IN"],
        ["04/05/2026", "80053", "$185.00", "$92.50", "$73.60", "$18.90", "IN"],
        ["04/05/2026", "93000", "$150.00", "$75.00", "$60.00", "$15.00", "IN"],
        # ── Intentional mismatch: bill=$1200, EOB=$800 → Module 3 ─────────────
        ["04/06/2026", "99291", "$800.00", "$400.00", "$320.00", "$80.00", "IN"],
        ["04/06/2026", "99231", "$2800.00", "$1400.00", "$1120.00", "$280.00", "IN"],
        ["04/06/2026", "99232", "$450.00", "$225.00", "$180.00", "$45.00", "IN"],
        ["04/07/2026", "71260", "$1850.00", "$925.00", "$740.00", "$185.00", "IN"],
        # ── Out-of-network → Module 4 No Surprises Act ────────────────────────
        ["04/07/2026", "99215", "$650.00", "$0.00", "$0.00", "$650.00", "OON"],
        ["04/07/2026", "99231", "$2800.00", "$1400.00", "$1120.00", "$280.00", "IN"],
        ["04/08/2026", "99490", "$300.00", "$150.00", "$120.00", "$30.00", "IN"],
    ]

    col_widths = [
        0.85 * inch,
        0.65 * inch,
        0.85 * inch,
        0.85 * inch,
        0.85 * inch,
        0.85 * inch,
        0.75 * inch,
    ]
    service_table = Table(service_data, colWidths=col_widths)
    service_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#006633")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F0F7F0")],
                ),
                # Highlight OON row in amber
                ("BACKGROUND", (0, 9), (-1, 9), colors.HexColor("#FFF3CD")),
                ("TEXTCOLOR", (6, 9), (6, 9), colors.HexColor("#CC0000")),
                ("FONTNAME", (0, 9), (-1, 9), "Helvetica-Bold"),
                # Highlight mismatch row (99291) in light blue
                ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#E3F2FD")),
                ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
            ]
        )
    )
    story.append(service_table)
    story.append(Spacer(1, 0.15 * inch))

    # ── Notes ────────────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            "* OON = Out-of-Network. CPT 99215 (Cardiology Consultation) was provided "
            "by an out-of-network provider during an emergency admission. "
            "This charge may be subject to No Surprises Act protections.",
            note_style,
        )
    )
    story.append(
        Paragraph(
            "** CPT 99291 (ER Physician Services): EOB billed amount ($800.00) differs "
            "from provider bill ($1,200.00). Please review this discrepancy.",
            note_style,
        )
    )
    story.append(Spacer(1, 0.2 * inch))

    # ── Summary ──────────────────────────────────────────────────────────────
    story.append(Paragraph("CLAIM SUMMARY", heading_style))
    summary_data = [
        ["Total Billed by Provider:", "$12,210.00"],
        ["Total Contractual Discount:", "-$5,385.00"],
        ["Total Plan Paid:", "-$2,919.60"],
        ["Total Member Responsibility:", "$3,905.40"],
        ["Less Copay Already Paid:", "-$50.00"],
        ["", ""],
        ["ESTIMATED AMOUNT YOU OWE:", "$3,855.40"],
    ]
    summary_table = Table(summary_data, colWidths=[4 * inch, 2.5 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6F4EA")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, -1), (-1, -1), 1, colors.grey),
                ("LINEABOVE", (0, -1), (-1, -1), 2, colors.HexColor("#006633")),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            "UnitedHealthcare PPO Gold | Member Services: 1-800-555-0199 | "
            "This is not a bill. Questions? Call member services.",
            ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, alignment=1),
        )
    )

    doc.build(story)

    print(f"✅ EOB created: {output_path}")
    print(f"📄 File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"\n🎯 Expected detectors to fire:")
    print(f"   Module 2 — Rate outlier:       CPT 99282 ($850 vs $47 Medicare = 1809%)")
    print(f"   Module 2 — Rate outlier:       CPT 99215 ($650 vs $82 Medicare = 793%)")
    print(
        f"   Module 3 — EOB reconciliation: CPT 99291 bill=$1200 vs EOB=$800 ($400 gap)"
    )
    print(f"   Module 4 — No Surprises Act:   CPT 99215 marked OON in EOB")
    print(f"\n✅ All other CPTs match exactly — no false positives")
    print(f"\n🚀 Upload both files:")
    print(f"   Bill: test_bill.pdf")
    print(f"   EOB:  test_eob.pdf")


if __name__ == "__main__":
    create_sample_eob()
