import streamlit as st
import pandas as pd
import plotly.express as px
import io
import zipfile
from core_evaluator import process_operations_logs, generate_employee_pdf
from ai_engine import SchoolOpsAIEngine

st.set_page_config(page_title="School Operations Evaluation System", layout="wide")

st.title("🏫 School Operations & Data Team Evaluation System")
st.markdown("Track data entry tasks, work types, completion statuses, and school coverage for operational staff.")

# Initialize AI Engine
ai_engine = SchoolOpsAIEngine()

# Sidebar Setup
st.sidebar.header("📥 Log Upload")
uploaded_file = st.sidebar.file_uploader("Upload Work Log Excel (.xlsx)", type=["xlsx"])

# Mock Generator with multi-tier sample data across all employees
if not uploaded_file:
    st.info("💡 Upload your work log file, or click below to simulate with sample data.")
    mock_logs = pd.DataFrame([
        # High Performer - Anil
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "Greenwood High", "WORK TYPE": "New Admission", "STATUS": "Completed", "REMARKS": "Processed 25 entries"},
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "Greenwood High", "WORK TYPE": "Fee configuration", "STATUS": "Completed", "REMARKS": "Set up term 1 fee structure"},
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "St. Xavier Academy", "WORK TYPE": "Report card publish", "STATUS": "Completed", "REMARKS": "Grade 10 published"},
        {"DATE": "2026-07-21", "NAME": "Anil Kumar", "SCHOOL NAME": "Oakridge School", "WORK TYPE": "Batch configuration", "STATUS": "Completed", "REMARKS": "Completed section data"},
        
        # Moderate Performer - Sita
        {"DATE": "2026-07-20", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "Absentees", "STATUS": "Completed", "REMARKS": "SMS alert sent"},
        {"DATE": "2026-07-20", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "HW Message sent", "STATUS": "Completed", "REMARKS": "Daily HW posted"},
        {"DATE": "2026-07-21", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "Data Checking", "STATUS": "Pending", "REMARKS": "Discrepancy found"},
        
        # Low Performer - Rajesh
        {"DATE": "2026-07-20", "NAME": "Rajesh Sharma", "SCHOOL NAME": "Apex International", "WORK TYPE": "Data Upload", "STATUS": "Pending", "REMARKS": "Incomplete data"},
        {"DATE": "2026-07-21", "NAME": "Rajesh Sharma", "SCHOOL NAME": "Apex International", "WORK TYPE": "Syllabus", "STATUS": "Pending", "REMARKS": "Awaiting response"},
        
        # Consistent Performer - Priya
        {"DATE": "2026-07-20", "NAME": "Priya Singh", "SCHOOL NAME": "Blossom Academy", "WORK TYPE": "Time Table", "STATUS": "Completed", "REMARKS": "Class schedules set"},
        {"DATE": "2026-07-21", "NAME": "Priya Singh", "SCHOOL NAME": "Blossom Academy", "WORK TYPE": "Sender ID Registration", "STATUS": "Completed", "REMARKS": "DLT approved"}
    ])
    st.dataframe(mock_logs, width="stretch")
    if st.button("Use Simulated Operations Sample Logs"):
        uploaded_file = "MOCK_ACTIVE"

# Main Data Processing & Tabs
if uploaded_file:
    df_raw = mock_logs if uploaded_file == "MOCK_ACTIVE" else pd.read_excel(uploaded_file, sheet_name=0)
    
    try:
        summary_df = process_operations_logs(df_raw)
    except Exception as e:
        st.error(f"Error processing log format. Make sure columns include: DATE, NAME, SCHOOL NAME, WORK TYPE, STATUS, REMARKS. Error: {e}")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["📊 Operations Overview", "🏆 Full Leaderboard & Metrics", "👤 Employee AI Diagnostics & PDFs"])

    with tab1:
        st.subheader("Team Task Performance Analytics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total System Tasks", len(df_raw))
        col2.metric("Total Staff Evaluated", len(summary_df))

        # ACCURATE SCHOOL COUNT RESOLVER
        school_col = [c for c in df_raw.columns if 'SCHOOL' in str(c).upper()]
        if school_col:
            total_schools = df_raw[school_col[0]].dropna().nunique()
        elif 'Schools Serviced' in summary_df.columns:
            total_schools = summary_df['Schools Serviced'].sum()
        else:
            total_schools = 0

        col3.metric("Schools Serviced", total_schools)
        col4.metric("Avg Team Score", f"{summary_df['Overall Score'].mean():.1f}/100")

        c1, c2 = st.columns(2)
        
        # Find work type column flexibly
        work_col = [c for c in df_raw.columns if 'WORK' in str(c).upper() or 'TYPE' in str(c).upper()]
        if work_col:
            work_counts = df_raw[work_col[0]].value_counts().reset_index()
            work_counts.columns = ['WORK TYPE', 'Count']
            fig_work = px.bar(work_counts.head(10), x='Count', y='WORK TYPE', orientation='h', title="Top Work Types Executed")
            c1.plotly_chart(fig_work, width="stretch")

        # Find status column flexibly
        status_col = [c for c in df_raw.columns if 'STATUS' in str(c).upper()]
        if status_col:
            fig_status = px.pie(df_raw, names=status_col[0], title="Overall Task Status Distribution", hole=0.4)
            c2.plotly_chart(fig_status, width="stretch")

    with tab2:
        st.subheader("Complete Employee Rankings")
        
        # Sort option toggle
        sort_order = st.radio("Sort Employees By Score:", ["Highest to Lowest", "Lowest to Highest"], horizontal=True)
        
        if sort_order == "Lowest to Highest":
            sorted_df = summary_df.sort_values(by="Overall Score", ascending=True)
        else:
            sorted_df = summary_df.sort_values(by="Overall Score", ascending=False)

        st.dataframe(
            sorted_df,
            column_config={
                "Overall Score": st.column_config.ProgressColumn(
                    "Overall Score",
                    help="Weighted performance score out of 100",
                    format="%.1f",
                    min_value=0,
                    max_value=100,
                ),
            },
            width="stretch",
            hide_index=True
        )

        fig_rank = px.bar(
            sorted_df, 
            x='NAME', 
            y='Overall Score', 
            color='Performance Tier', 
            title="Full Employee Score Distribution"
        )
        st.plotly_chart(fig_rank, width="stretch")

    with tab3:
        st.subheader("Individual Performance Diagnostics & PDF Generation")
        
        all_employees = summary_df['NAME'].tolist()
        selected_emp = st.selectbox("Select Operations Staff Member:", all_employees)
        emp_row = summary_df[summary_df['NAME'] == selected_emp].iloc[0]

        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric(label="Overall Score", value=f"{emp_row['Overall Score']:.1f} / 100")
            st.caption(f"Tier: **{emp_row['Performance Tier']}**")
            st.write(f"- **Total Tasks Handled:** {emp_row['Total Tasks']}")
            st.write(f"- **Completion Rate:** {emp_row['Completion Rate (%)']:.1f}%")
            st.write(f"- **High-Complexity Tasks:** {emp_row['Complex Tasks']}")
            st.write(f"- **Schools Covered:** {emp_row['Schools Serviced']}")
            st.write(f"- **Pending Tasks:** {emp_row['Pending Tasks']}")

        with c2:
            st.subheader(f"AI Audit & PDF for {selected_emp}")
            if st.button(f"Generate AI Audit Report"):
                with st.spinner("Generating performance evaluation..."):
                    ai_report = ai_engine.generate_evaluation_report(emp_row.to_dict())

                    for title, content in ai_report.items():
                        with st.expander(f"📋 {title}"):
                            st.write(content)

                    pdf_file = generate_employee_pdf(emp_row.to_dict(), ai_report)
                    st.download_button(
                        label=f"📥 Download PDF Evaluation ({selected_emp})",
                        data=pdf_file,
                        file_name=f"Ops_Evaluation_{selected_emp.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )

        st.divider()
        
        # BULK DOWNLOAD FEATURE
        st.subheader("📦 Bulk PDF Export for ALL Staff Members")
        st.write("Generate and download individual evaluation PDFs for every employee in a single `.zip` file.")
        
        if st.button("Generate Bulk PDFs for All Staff"):
            with st.spinner(f"Building PDF reports for all {len(summary_df)} employees..."):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for _, row in summary_df.iterrows():
                        emp_data = row.to_dict()
                        report = ai_engine.generate_evaluation_report(emp_data)
                        pdf_bytes = generate_employee_pdf(emp_data, report)
                        file_name = f"Ops_Evaluation_{emp_data['NAME'].replace(' ', '_')}.pdf"
                        zip_file.writestr(file_name, pdf_bytes)
                
                zip_buffer.seek(0)
                st.download_button(
                    label="📥 Download ALL Employee Reports (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="All_Staff_Operations_Evaluations.zip",
                    mime="application/zip"
                )