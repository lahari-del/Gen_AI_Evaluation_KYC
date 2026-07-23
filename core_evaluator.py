import pandas as pd
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

HIGH_COMPLEXITY_WORK = [
    "BATCH CONFIGURATION", "FEE CONFIGURATION", "SYLLABUS", "TIME TABLE",
    "REPORT CARD PUBLISH", "REPORT CARD CHECKING", "DATA UPLOAD",
    "SENDER ID REGISTRATION", "DLT REGISTRATION", "CLASS TEACHER ASSIGNED"
]

def process_operations_logs(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans raw logs or pre-aggregated summary sheets and guarantees non-negative pending values."""
    df = df.copy()
    
    # 1. Standardize column headers
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Clean string values in all text columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Detect if the uploaded sheet is already a summary format
    cols_upper = list(df.columns)
    is_summary = any(k in cols_upper for k in ['TOTAL TASKS', 'COMPLETED TASKS', 'PENDING TASKS', 'OVERALL SCORE'])

    if is_summary:
        total_col = [c for c in df.columns if 'TOTAL' in c][0]
        comp_col = [c for c in df.columns if 'COMPLETED' in c][0]
        complex_cols = [c for c in df.columns if 'COMPLEX' in c]
        school_cols = [c for c in df.columns if 'SCHOOL' in c]

        complex_col = complex_cols[0] if complex_cols else None
        school_col = school_cols[0] if school_cols else None

        name_col = 'NAME' if 'NAME' in df.columns else df.columns[0]

        summary = pd.DataFrame({
            'NAME': df[name_col],
            'Total_Tasks': pd.to_numeric(df[total_col], errors='coerce').fillna(0).astype(int),
            'Completed_Tasks': pd.to_numeric(df[comp_col], errors='coerce').fillna(0).astype(int),
            'Complex_Tasks': pd.to_numeric(df[complex_col], errors='coerce').fillna(0).astype(int) if complex_col else 0,
            'Schools_Serviced': pd.to_numeric(df[school_col], errors='coerce').fillna(0).astype(int) if school_col else 1
        })
    else:
        # Process raw log sheets
        status_str = df['STATUS'].astype(str).str.upper() if 'STATUS' in df.columns else pd.Series([""] * len(df))
        df['IS_COMPLETED'] = status_str.str.contains('COMPLETE|DONE|PUBLISH|SENT|SUCCESS|TRUE|1', regex=True)
        
        work_type_str = df['WORK TYPE'].astype(str).str.upper() if 'WORK TYPE' in df.columns else pd.Series([""] * len(df))
        df['IS_HIGH_COMPLEX'] = work_type_str.isin(HIGH_COMPLEXITY_WORK)
        
        school_col = [c for c in df.columns if 'SCHOOL' in c]
        school_field = school_col[0] if school_col else ('SCHOOL NAME' if 'SCHOOL NAME' in df.columns else None)

        if 'NAME' not in df.columns:
            df['NAME'] = "Unknown Employee"

        agg_dict = {
            'IS_COMPLETED': ['count', 'sum'],
            'IS_HIGH_COMPLEX': 'sum'
        }
        if school_field and school_field in df.columns:
            agg_dict[school_field] = 'nunique'

        summary = df.groupby('NAME').agg(agg_dict).reset_index()
        
        if school_field and school_field in df.columns:
            summary.columns = ['NAME', 'Total_Tasks', 'Completed_Tasks', 'Complex_Tasks', 'Schools_Serviced']
        else:
            summary.columns = ['NAME', 'Total_Tasks', 'Completed_Tasks', 'Complex_Tasks']
            summary['Schools_Serviced'] = 1

    # 2. GUARANTEED NON-NEGATIVE MATH RE-CALCULATION
    # Ensure Total Tasks is at least equal to Completed Tasks
    summary['Total Tasks'] = np.maximum(summary['Total_Tasks'], summary['Completed_Tasks'])
    summary['Completed Tasks'] = summary['Completed_Tasks']

    # HARD OVERRIDE: Force Pending Tasks to be strictly >= 0
    summary['Pending Tasks'] = np.maximum(0, summary['Total Tasks'] - summary['Completed Tasks']).astype(int)
    
    # Completion Rate %
    summary['Completion Rate (%)'] = np.where(
        summary['Total Tasks'] > 0,
        (summary['Completed Tasks'] / summary['Total Tasks']) * 100.0,
        0.0
    ).clip(0, 100.0).round(2)

    summary['Complex Tasks'] = summary['Complex_Tasks'].fillna(0).astype(int)
    summary['Schools Serviced'] = summary['Schools_Serviced'].fillna(0).astype(int)

    # 3. RELATIVE METRICS & PERFORMANCE TIERS
    max_tasks = max(summary['Total Tasks'].max(), 1)
    max_complex = max(summary['Complex Tasks'].max(), 1)
    max_schools = max(summary['Schools Serviced'].max(), 1)

    summary['Volume Score'] = (summary['Total Tasks'] / max_tasks) * 100.0
    summary['Complexity Score'] = (summary['Complex Tasks'] / max_complex) * 100.0
    summary['Reach Score'] = (summary['Schools Serviced'] / max_schools) * 100.0
    
    summary['Overall Score'] = (
        (summary['Completion Rate (%)'] * 0.35) +
        (summary['Volume Score'] * 0.35) +
        (summary['Complexity Score'] * 0.20) +
        (summary['Reach Score'] * 0.10)
    ).round(2)

    def assign_tier(score):
        if score >= 85: return 'High Achiever'
        elif score >= 65: return 'Consistent Performer'
        elif score >= 45: return 'Needs Improvement'
        else: return 'Critical Attention Required'

    summary['Performance Tier'] = summary['Overall Score'].apply(assign_tier)
    
    display_cols = [
        'NAME', 'Total Tasks', 'Completed Tasks', 'Pending Tasks',
        'Complex Tasks', 'Schools Serviced', 'Completion Rate (%)',
        'Overall Score', 'Performance Tier'
    ]
    
    sorted_summary = summary.sort_values(
        by=['Overall Score', 'Total Tasks', 'Complex Tasks'],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    return sorted_summary[display_cols]


def generate_employee_pdf(emp_data: dict, ai_report: dict) -> bytes:
    """Generates an official PDF evaluation report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1F4E78'))
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#1F4E78'), spaceBefore=10)
    body_style = ParagraphStyle('BodyTextCustom', parent=styles['Normal'], fontSize=10, leading=14)

    elements = [
        Paragraph(f"Operations Audit Report: {emp_data['NAME']}", title_style),
        Spacer(1, 10)
    ]

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

    if isinstance(ai_report, dict):
        for title, section_content in ai_report.items():
            elements.append(Paragraph(f"<b>{title.upper()}</b>", heading_style))
            elements.append(Spacer(1, 4))
            for line in str(section_content).split('\n'):
                if line.strip():
                    elements.append(Paragraph(line.strip(), body_style))
            elements.append(Spacer(1, 10))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()