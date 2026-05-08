#!/usr/bin/env python3
"""
Generate a sample EOB (Explanation of Benefits) PDF for testing MediCheck.
Matches the test_bill.pdf generated earlier.
Includes network status flags to trigger Module 3 (EOB Reconciliation)
and Module 4 (No Surprises Act).
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import os


def create_sample_eob():
    output_path = "/Users/shifalisrivastava/Documents/Capstone/MediCheck/test_eob.pdf"

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # ── Styles ──────────────────────────────────────────────
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

    # ── Header ───────────────────────────────────────────────
    story.append(Paragraph("EXPLANATION OF BENEFITS", title_style))
    story.append(Paragraph("This is not a bill. Keep for your records.", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    # ── Insurer info ─────────────────────────────────────────
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

    # ── Member info ──────────────────────────────────────────
    story.append(Paragraph("MEMBER INFORMATION", heading_style))
    member_data = [
        ["Member Name:", "John Michael Thompson", "Member ID:", "MH-789456123"],
        ["Date of Birth:", "06/15/1975", "Plan:", "PPO Gold"],
        ["Provider:", "Metropolitan Hospital Center", "NPI:", "1234567890"],
        ["Service Period:", "04/05/2026 - 04/08/2026", "Copay:", "$50.00"],
    ]
    member_table = Table(member_data, colWidths=[1.5 * inch, 2.2 * inch, 1.5 * inch, 2.3 * inch])
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

    # ── Benefits detail ──────────────────────────────────────
    story.append(Paragraph("BENEFITS DETAIL", heading_style))

    service_data = [
        [
            "Date",
            "CPT",
            "Billed",
            "Discount",
            "Plan Paid",
            "Your Cost",
            "Network",
        ],
        # ── In-network charges ───────────────────────────────
        ["04/05/2026", "99282", "$850.00", "$637.50", "$170.00", "$42.50", "IN"],
        ["04/05/2026", "71020", "$425.00", "$255.00", "$136.00", "$34.00", "IN"],
        ["04/05/2026", "80053", "$185.00", "$92.50", "$73.60", "$18.90", "IN"],
        ["04/05/2026", "93000", "$150.00", "$75.00", "$60.00", "$15.00", "IN"],
        # ── EOB shows LOWER amount than bill for 99291 ────────
        # Bill says $1200, EOB says $800 → triggers Module 3
        ["04/06/2026", "99291", "$800.00", "$400.00", "$320.00", "$80.00", "IN"],
        ["04/06/2026", "99231", "$2,800.00", "$1,400.00", "$1,120.00", "$280.00", "IN"],
        ["04/06/2026", "99232", "$450.00", "$225.00", "$180.00", "$45.00", "IN"],
        ["04/07/2026", "71260", "$1,850.00", "$925.00", "$740.00", "$185.00", "IN"],
        # ── Out-of-network cardiology consult ─────────────────
        # Triggers Module 4 (No Surprises Act) — emergency context
        ["04/07/2026", "99215", "$650.00", "$0.00", "$0.00", "$650.00", "OON"],
        ["04/07/2026", "99231", "$2,800.00", "$1,400.00", "$1,120.00", "$280.00", "IN"],
        ["04/08/2026", "99490", "$300.00", "$150.00", "$120.00", "$30.00", "IN"],
    ]

    col_widths = [0.9 * inch, 0.7 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch]
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
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F7F0")]),
                # Highlight OON row in amber
                ("BACKGROUND", (0, 10), (-1, 10), colors.HexColor("#FFF3CD")),
                ("TEXTCOLOR", (6, 10), (6, 10), colors.HexColor("#CC0000")),
                ("FONTNAME", (0, 10), (-1, 10), "Helvetica-Bold"),
            ]
        )
    )
    story.append(service_table)
    story.append(Spacer(1, 0.1 * inch))

    # ── OON note ─────────────────────────────────────────────
    story.append(
        Paragraph(
            "* OON = Out-of-Network. CPT 99215 (Cardiology Consultation) was provided by "
            "an out-of-network provider. You may be responsible for the full billed amount. "
            "This charge may be subject to the No Surprises Act protections.",
            note_style,
        )
    )
    story.append(Spacer(1, 0.2 * inch))

    # ── Summary ──────────────────────────────────────────────
    story.append(Paragraph("CLAIM SUMMARY", heading_style))
    summary_data = [
        ["Total Billed by Provider:", "$12,710.00"],
        ["Total Contractual Discount:", "-$5,559.00"],
        ["Total Plan Paid:", "-$4,039.60"],
        ["Total Member Responsibility:", "$3,110.40"],
        ["Less Copay Already Paid:", "-$50.00"],
        ["", ""],
        ["ESTIMATED AMOUNT YOU OWE:", "$3,060.40"],
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

    # ── Footer ───────────────────────────────────────────────
    story.append(
        Paragraph(
            "UnitedHealthcare PPO Gold | Member Services: 1-800-555-0199 | "
            "This is not a bill. Questions? Call member services.",
            ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, alignment=1),
        )
    )

    doc.build(story)

    print(f"✅ Sample EOB created: {output_path}")
    print(f"📄 File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"\n📝 EOB Details:")
    print(f"   Member: John Michael Thompson")
    print(f"   Insurer: UnitedHealthcare PPO Gold")
    print(f"   Service Period: 04/05/2026 - 04/08/2026")
    print(f"\n🎯 Expected detectors to fire:")
    print(f"   Module 1 — Duplicate charge: 99231 appears twice (same CPT, different dates — should NOT flag)")
    print(f"   Module 2 — Rate outlier: 99282, 99291, 99215 all above 300% Medicare")
    print(f"   Module 3 — EOB reconciliation: 99291 billed $1200 vs EOB $800 → mismatch")
    print(f"   Module 4 — No Surprises Act: 99215 marked OON in EOB → potential violation")
    print(f"\n🚀 Upload both files to MediCheck:")
    print(f"   Bill: test_bill.pdf")
    print(f"   EOB:  test_eob.pdf")


if __name__ == "__main__":
    create_sample_eob()