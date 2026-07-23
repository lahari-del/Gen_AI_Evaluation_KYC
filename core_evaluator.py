import pandas as pd
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

HIGH_COMPLEXITY_WORK = [
    "Batch configuration", "Fee configuration", "Syllabus", "Time Table",
    "Report card publish", "Report card checking", "Data Upload",
    "Sender ID Registration", "DLT Registration", "Class Teacher assigned"
]

def process_operations_logs(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates raw task entries into accurate employee performance metrics."""
    df = df.copy()
    
    # Clean up column names (strip whitespace and uppercase)
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Clean Status column
    df['IS_COMPLETED'] = df['STATUS'].astype(str).str.upper().str.contains('COMPLETE|DONE|PUBLISH|SENT|SUCCESS|TRUE|1')
    
    # Classify complexity
    df['WORK_TYPE_STR'] = df['WORK TYPE'].astype(str) if 'WORK TYPE' in df.columns else ""
    df['IS_HIGH_COMPLEX'] = df['WORK_TYPE_STR'].isin(HIGH_COMPLEXITY_WORK)
    
    school_col = [c for c in df.columns if 'SCHOOL' in c]
    school_field = school_col[0] if school_col else 'SCHOOL NAME'

    # Group & calculate base metrics
    summary = df.groupby('NAME').agg(
        Total_Tasks=('STATUS', 'count'),
        Completed_Tasks=('IS_COMPLETED', 'sum'),
        Complex_Tasks=('IS_HIGH_COMPLEX', 'sum'),
        Schools_Serviced=(school_field, 'nunique') if school_field in df.columns else ('STATUS', lambda x: 1)
    ).reset_index()

    # DATA ACCURACY FIXES:
    # 1. Completed tasks can never exceed Total Tasks
    summary['Completed Tasks'] = np.minimum(summary['Completed_Tasks'], summary['Total_Tasks'])
    summary['Total Tasks'] = summary['Total_Tasks']
    
    # 2. Pending Tasks can never be negative
    summary['Pending Tasks'] = np.maximum(0, summary['Total Tasks'] - summary['Completed Tasks'])
    
    # 3. Completion Rate capped at 100.0% max
    summary['Completion Rate (%)'] = (summary['Completed Tasks'] / np.maximum(1, summary['Total Tasks'])) * 100.0
    summary['Completion Rate (%)'] = summary['Completion Rate (%)'].clip(upper=100.0)

    summary['Complex Tasks'] = summary['Complex_Tasks']
    summary['Schools Serviced'] = summary['Schools_Serviced']

    # Weighted Component Scores (0-100)
    summary['Volume Score'] = (summary['Total Tasks'] / 50.0).clip(upper=1.0) * 100.0
    summary['Complexity Score'] = (summary['Complex Tasks'] / 10.0).clip(upper=1.0) * 100.0
    summary['Reach Score'] = (summary['Schools Serviced'] / 5.0).clip(upper=1.0) * 100.0
    
    # Overall Score
    summary['Overall Score'] = (
        (summary['Completion Rate (%)'] * 0.40) +
        (summary['Volume Score'] * 0.30) +
        (summary['Complexity Score'] * 0.20) +
        (summary['Reach Score'] * 0.10)
    ).round(2)

    def assign_tier(score):
        if score >= 88: return 'High Achiever'
        elif score >= 75: return 'Consistent Performer'
        elif score >= 60: return 'Needs Improvement'
        else: return 'Critical Attention Required'

    summary['Performance Tier'] = summary['Overall Score'].apply(assign_tier)
    
    # Clean export columns
    display_cols = [
        'NAME', 'Total Tasks', 'Completed Tasks', 'Pending Tasks', 
        'Complex Tasks', 'Schools Serviced', 'Completion Rate (%)', 
        'Overall Score', 'Performance Tier'
    ]
    
    return summary[display_cols].sort_values(by='Overall Score', ascending=False).reset_index(drop=True)


def generate_employee_pdf(emp_data: dict, ai_report: dict) -> bytes:
    """Generates an official PDF evaluation report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1F4E78'))
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#1F4E78'), spaceBefore=10)
    body_style = ParagraphStyle('BodyTextCustom', parent=styles['Normal'], fontSize=10, leading=14)

    elements = []

    elements.append(Paragraph(f"Operations Audit Report: {emp_data['NAME']}", title_style))
    elements.append(Spacer(1, 10))

    table_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Overall Performance Score", f"{emp_data['Overall Score']:.1f} / 100", "Performance Tier", str(emp_data['Performance Tier'])],
        ["Total Tasks Handled", str(emp_data['Total Tasks']), "Completion Rate", f"{emp_data['Completion Rate (%)']:.1f}%"],
        ["High Complexity Tasks", str(emp_data['Complex Tasks']), "Schools Serviced", str(emp_data['Schools Serviced'])]
    ]
    
    t = Table(table_data, colWidths=[150, 120, 150, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F4E78')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))

    for title, section_content in ai_report.items():
        elements.append(Paragraph(f"<b>{title.upper()}</b>", heading_style))
        elements.append(Spacer(1, 4))
        for line in section_content.split('\n'):
            if line.strip():
                elements.append(Paragraph(line.strip(), body_style))
        elements.append(Spacer(1, 10))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()