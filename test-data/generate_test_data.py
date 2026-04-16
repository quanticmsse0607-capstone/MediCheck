#!/usr/bin/env python3
"""
Generate a sample medical bill PDF for testing MediCheck
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from datetime import datetime, timedelta
import os

def create_sample_bill():
    """Create a realistic sample medical bill PDF"""
    
    # Output path
    output_path = "/Users/shifalisrivastava/Documents/Capstone/MediCheck/test_bill.pdf"
    
    # Create PDF document
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#003366'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # ===== Header Section =====
    story.append(Paragraph("HOSPITAL SERVICES BILL", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Provider info
    provider_data = [
        ["METROPOLITAN HOSPITAL CENTER", "Bill Date: 04/15/2026"],
        ["123 Medical Park Drive", "Service Period: 04/01/2026 - 04/15/2026"],
        ["New York, NY 10001", "Account #: HB-2026-45892"],
        ["Phone: (212) 555-0100", ""]
    ]
    
    provider_table = Table(provider_data, colWidths=[3.5*inch, 3*inch])
    provider_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(provider_table)
    story.append(Spacer(1, 0.3*inch))
    
    # ===== Patient Information =====
    story.append(Paragraph("PATIENT INFORMATION", heading_style))
    
    patient_data = [
        ["Patient Name:", "John Michael Thompson", "Member ID:", "MH-789456123"],
        ["Date of Birth:", "06/15/1975 (Age 50)", "Group #:", "EMP-2024-001"],
        ["Address:", "456 Main Street, New York, NY 10002", "Plan:", "PPO Gold"],
        ["Insurance ID:", "UHC-456789012", "Copay:", "$50.00"]
    ]
    
    patient_table = Table(patient_data, colWidths=[1.5*inch, 2.2*inch, 1.5*inch, 2.3*inch])
    patient_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E6E6E6')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#E6E6E6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 0.3*inch))
    
    # ===== Service Details =====
    story.append(Paragraph("SERVICE DETAILS & CHARGES", heading_style))
    
    service_data = [
        ["Date", "Service Description", "CPT Code", "Units", "Rate", "Amount"],
        ["04/05/2026", "Emergency Room Visit - Level 3", "99282", "1", "$850.00", "$850.00"],
        ["04/05/2026", "Chest X-ray (2 views)", "71020", "1", "$425.00", "$425.00"],
        ["04/05/2026", "Comprehensive Metabolic Panel", "80053", "1", "$185.00", "$185.00"],
        ["04/05/2026", "Electrocardiogram", "93000", "1", "$150.00", "$150.00"],
        ["04/06/2026", "ER Physician Services - 2 hours", "99291", "1", "$1,200.00", "$1,200.00"],
        ["04/06/2026", "Hospital Room - Semi-private (1 night)", "99231", "1", "$2,800.00", "$2,800.00"],
        ["04/06/2026", "Nursing Care", "99232", "1", "$450.00", "$450.00"],
        ["04/07/2026", "CT Scan - Chest with contrast", "71260", "1", "$1,850.00", "$1,850.00"],
        ["04/07/2026", "Cardiology Consultation", "99215", "1", "$650.00", "$650.00"],
        ["04/07/2026", "Hospital Room - Semi-private (1 night)", "99231", "1", "$2,800.00", "$2,800.00"],
        ["04/08/2026", "Discharge Planning Service", "99490", "1", "$300.00", "$300.00"],
    ]
    
    service_table = Table(service_data, colWidths=[1*inch, 2.8*inch, 0.9*inch, 0.7*inch, 1*inch, 1*inch])
    service_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
    ]))
    story.append(service_table)
    story.append(Spacer(1, 0.2*inch))
    
    # ===== Summary Section =====
    story.append(Paragraph("BILLING SUMMARY", heading_style))
    
    summary_data = [
        ["Total Charges:", "$12,710.00"],
        ["Less: Contractual Adjustment (15%)", "-$1,906.50"],
        ["Subtotal After Adjustment:", "$10,803.50"],
        ["Insurance Payment (80% - PPO):", "-$8,642.80"],
        ["Patient Responsibility:", "$2,160.70"],
        ["Previous Balance:", "$0.00"],
        ["Payments Received:", "$0.00"],
        ["", ""],
        ["BALANCE DUE:", "$2,160.70"],
    ]
    
    # Color code the final balance
    summary_table = Table(summary_data, colWidths=[4*inch, 2.5*inch])
    summary_style = [
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#FFE6E6')),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#CC0000')),
        ('GRID', (0, -2), (-1, -1), 1, colors.grey),
        ('LINEABOVE', (0, 2), (-1, 2), 2, colors.black),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.grey),
    ]
    summary_table.setStyle(TableStyle(summary_style))
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # ===== Important Notes =====
    story.append(Paragraph("IMPORTANT INFORMATION", heading_style))
    
    notes = [
        "• This bill reflects in-network contracted rates. Your insurance plan applies 80% coverage for in-network services.",
        "• Contractual adjustments of 15% were applied based on your PPO agreement.",
        "• Payment is due within 30 days of receipt. Please reference Account #HB-2026-45892 on check.",
        "• If you have questions about specific charges, please contact our billing department.",
        "• NOTE: We have flagged several charges for review - some appear higher than typical industry standards.",
        "  Specifically: ER Physician Services (99291) at $1,200.00 appears to be above typical rates.",
    ]
    
    for note in notes:
        story.append(Paragraph(note, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    story.append(Spacer(1, 0.3*inch))
    
    # ===== Footer =====
    footer_text = "Metropolitan Hospital Center | 123 Medical Park Drive, New York, NY 10001 | Phone: (212) 555-0100"
    story.append(Paragraph(footer_text, ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, alignment=1)))
    
    # Build PDF
    doc.build(story)
    
    print(f"✅ Sample medical bill created: {output_path}")
    print(f"📄 File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"\n📝 Bill Details:")
    print(f"   Patient: John Michael Thompson")
    print(f"   Service Period: 04/01/2026 - 04/15/2026")
    print(f"   Total Charges: $12,710.00")
    print(f"   Balance Due: $2,160.70")
    print(f"\n🚀 You can now upload this bill to MediCheck!")
    print(f"   Frontend: http://localhost:5173")

if __name__ == "__main__":
    create_sample_bill()
