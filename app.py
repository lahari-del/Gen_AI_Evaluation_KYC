import streamlit as st
import pandas as pd
import plotly.express as px
from core_evaluator import process_operations_logs, generate_employee_pdf
from ai_engine import SchoolOpsAIEngine

st.set_page_config(page_title="School Operations Evaluation System", layout="wide")

st.title("🏫 School Operations & Data Team Evaluation System")
st.markdown("Track data entry tasks, work types, completion statuses, and school coverage for operational staff.")

ai_engine = SchoolOpsAIEngine()

st.sidebar.header("📥 Log Upload")
uploaded_file = st.sidebar.file_uploader("Upload Work Log Excel (.xlsx)", type=["xlsx"])

# Mock Generator reflecting your exact image fields
if not uploaded_file:
    st.info("💡 Upload your work log file, or click below to simulate with sample data.")
    mock_logs = pd.DataFrame([
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "Greenwood High", "WORK TYPE": "New Admission", "STATUS": "Completed", "REMARKS": "Processed 25 entries"},
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "Greenwood High", "WORK TYPE": "Fee configuration", "STATUS": "Completed", "REMARKS": "Set up term 1 fee structure"},
        {"DATE": "2026-07-20", "NAME": "Anil Kumar", "SCHOOL NAME": "St. Xavier Academy", "WORK TYPE": "Report card publish", "STATUS": "Completed", "REMARKS": "Grade 10 published"},
        {"DATE": "2026-07-21", "NAME": "Anil Kumar", "SCHOOL NAME": "Oakridge School", "WORK TYPE": "Batch configuration", "STATUS": "Pending", "REMARKS": "Awaiting section data"},
        
        {"DATE": "2026-07-20", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "Absentees", "STATUS": "Completed", "REMARKS": "SMS alert sent"},
        {"DATE": "2026-07-20", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "HW Message sent", "STATUS": "Completed", "REMARKS": "Daily HW posted"},
        {"DATE": "2026-07-21", "NAME": "Sita Verma", "SCHOOL NAME": "DPS Public School", "WORK TYPE": "Data Checking", "STATUS": "Pending", "REMARKS": "Discrepancy found"}
    ])
    st.dataframe(mock_logs, use_container_width=True)
    if st.button("Use Simulated Operations Sample Logs"):
        uploaded_file = "MOCK_ACTIVE"

if uploaded_file:
    df_raw = mock_logs if uploaded_file == "MOCK_ACTIVE" else pd.read_excel(uploaded_file)
    
    # Process Logs
    try:
        summary_df = process_operations_logs(df_raw)
    except Exception as e:
        st.error(f"Error processing log format. Make sure columns include: DATE, NAME, SCHOOL NAME, WORK TYPE, STATUS, REMARKS. Error: {e}")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["📊 Operations Overview", "🏆 Leaderboard & Metrics", "👤 Employee AI Diagnostics"])

    with tab1:
        st.subheader("Team Task Performance Analytics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total System Tasks", len(df_raw))
        col2.metric("Schools Serviced", df_raw['SCHOOL NAME'].nunique())
        col3.metric("Avg Team Score", f"{summary_df['Overall Score'].mean():.1f}/100")

        c1, c2 = st.columns(2)
        
        # Most Common Work Types
        work_counts = df_raw['WORK TYPE'].value_counts().reset_index()
        work_counts.columns = ['WORK TYPE', 'Count']
        fig_work = px.bar(work_counts.head(10), x='Count', y='WORK TYPE', orientation='h', title="Top 10 Work Types Executed")
        c1.plotly_chart(fig_work, use_container_width=True)

        # Work Status Breakdown
        fig_status = px.pie(df_raw, names='STATUS', title="Overall Task Status Distribution", hole=0.4)
        c2.plotly_chart(fig_status, use_container_width=True)

    with tab2:
        st.subheader("Employee Merit Standings")
        st.dataframe(summary_df.style.background_gradient(subset=['Overall Score'], cmap='Blues'), use_container_width=True)

        fig_rank = px.bar(summary_df, x='NAME', y='Overall Score', color='Performance Tier', title="Overall Performance Score Comparison")
        st.plotly_chart(fig_rank, use_container_width=True)

    with tab3:
        st.subheader("Individual Performance Diagnostic")
        selected_emp = st.selectbox("Select Operations Member:", summary_df['NAME'].tolist())
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
            st.subheader("AI Performance Narrative & PDF Export")
            if st.button(f"Generate AI Audit for {selected_emp}"):
                with st.spinner("Analyzing log patterns and building evaluation report..."):
                    ai_report = ai_engine.generate_evaluation_report(emp_row.to_dict())

                    for title, content in ai_report.items():
                        with st.expander(f"📋 {title}"):
                            st.write(content)

                    # Create downloadable PDF
                    pdf_file = generate_employee_pdf(emp_row.to_dict(), ai_report)
                    st.download_button(
                        label=f"📥 Download Official PDF Evaluation ({selected_emp})",
                        data=pdf_file,
                        file_name=f"Ops_Evaluation_{selected_emp.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )