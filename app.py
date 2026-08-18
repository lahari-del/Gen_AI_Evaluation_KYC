import streamlit as st
import pandas as pd
import plotly.express as px
import io
import zipfile
from core_evaluator import process_operations_logs, generate_employee_pdf
from ai_engine import SchoolOpsAIEngine

st.set_page_config(page_title="School Operations Evaluation System", layout="wide")

st.title("🏫 School Operations & Data Team Evaluation System")
st.markdown("Track data entry tasks, speed targets, forms volume, work types, and school coverage for operational staff.")

# Initialize AI Engine
ai_engine = SchoolOpsAIEngine()

# Sidebar Setup
st.sidebar.header("📥 Log Upload")
uploaded_file = st.sidebar.file_uploader("Upload Work Log Excel (.xlsx or .csv)", type=["xlsx", "csv"])

if not uploaded_file:
    st.info("💡 Upload your work log file, or click below to simulate with sample data.")
    mock_logs = pd.DataFrame([
        {"DATE": "2026-07-20", "NAME": "Pranay", "SCHOOL NAME": "Greenwood High", "WORK TYPE": "New Admission", "STATUS": "Completed", "TARGET": 70},
        {"DATE": "2026-07-20", "NAME": "Pranay", "SCHOOL NAME": "Oakridge", "WORK TYPE": "Fee configuration", "STATUS": "Completed", "TARGET": 70},
        {"DATE": "2026-07-20", "NAME": "Sumanth", "SCHOOL NAME": "DPS Public", "WORK TYPE": "Absentees", "STATUS": "Completed", "TARGET": 50},
        {"DATE": "2026-07-21", "NAME": "Sumanth", "SCHOOL NAME": "DPS Public", "WORK TYPE": "Data Checking", "STATUS": "Pending", "TARGET": 50}
    ])
    st.dataframe(mock_logs, width="stretch")
    if st.button("Use Simulated Operations Sample Logs"):
        uploaded_file = "MOCK_ACTIVE"

# Main Data Processing
if uploaded_file:
    if uploaded_file == "MOCK_ACTIVE":
        df_raw = mock_logs
    else:
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

    try:
        summary_df = process_operations_logs(df_raw)

        # -------------------------------------------------------------
        # 🛡️ HARD OVERRIDE: FORCE PENDING TASKS TO NEVER BE NEGATIVE
        # -------------------------------------------------------------
        if 'Pending Tasks' in summary_df.columns:
            summary_df['Pending Tasks'] = summary_df['Pending Tasks'].apply(lambda x: max(0, int(x) if pd.notnull(x) else 0))

    except Exception as e:
        st.error(f"Error processing log format: {e}")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["📊 Operations Overview", "🏆 Full Leaderboard & Metrics", "👤 Employee AI Diagnostics & PDFs"])

    with tab1:
        st.subheader("Team Task & Target Speed Performance Analytics")
        
        # Macro KPIs (Includes Add-on Specs: Forms & Target Speed)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total System Tasks", int(summary_df['Total Tasks'].sum()))
        col2.metric("Total Forms Processed", int(summary_df['Total Forms'].sum()) if 'Total Forms' in summary_df.columns else int(summary_df['Total Tasks'].sum()))
        
        speed_val = f"{summary_df['Speed Rate (%)'].mean():.1f}%" if 'Speed Rate (%)' in summary_df.columns else "N/A"
        col3.metric("Avg Speed vs Target", speed_val)

        # Accurate school count across dataset
        school_col = [c for c in df_raw.columns if 'SCHOOL' in str(c).upper()]
        if school_col:
            total_schools = df_raw[school_col[0]].dropna().nunique()
        else:
            total_schools = int(summary_df['Schools Serviced'].sum())

        col4.metric("Schools Serviced", total_schools)
        col5.metric("Avg Team Score", f"{summary_df['Overall Score'].mean():.1f}/100")

        st.divider()

        c1, c2 = st.columns(2)
        work_col = [c for c in df_raw.columns if 'WORK' in str(c).upper() or 'TYPE' in str(c).upper()]
        if work_col:
            work_counts = df_raw[work_col[0]].astype(str).str.strip().value_counts().reset_index()
            work_counts.columns = ['WORK TYPE', 'Count']
            fig_work = px.bar(work_counts.head(10), x='Count', y='WORK TYPE', orientation='h', title="Top Work Types Executed (Calls, Absentees, Configs)")
            c1.plotly_chart(fig_work, width="stretch")

        status_col = [c for c in df_raw.columns if 'STATUS' in str(c).upper()]
        if status_col:
            fig_status = px.pie(df_raw, names=status_col[0], title="Overall Task Status Distribution", hole=0.4)
            c2.plotly_chart(fig_status, width="stretch")

    with tab2:
        st.subheader("Complete Employee Rankings & Speed Targets")
        
        sort_order = st.radio("Sort Employees By Score:", ["Highest to Lowest", "Lowest to Highest"], horizontal=True)
        
        if sort_order == "Lowest to Highest":
            sorted_df = summary_df.sort_values(
                by=["Overall Score", "Total Tasks", "Complex Tasks"],
                ascending=[True, True, True]
            ).reset_index(drop=True)
        else:
            sorted_df = summary_df.sort_values(
                by=["Overall Score", "Total Tasks", "Complex Tasks"],
                ascending=[False, False, False]
            ).reset_index(drop=True)

        # Configure Column Formats Including Add-on Specifications
        column_configuration = {
            "Overall Score": st.column_config.ProgressColumn(
                "Overall Score",
                help="Relative score based on completion, volume, complexity, and school reach",
                format="%.1f",
                min_value=0,
                max_value=100,
            ),
            "Completion Rate (%)": st.column_config.NumberColumn(
                "Completion Rate (%)",
                format="%.1f%%"
            )
        }

        if "Speed Rate (%)" in sorted_df.columns:
            column_configuration["Speed Rate (%)"] = st.column_config.NumberColumn(
                "Speed Rate (%)",
                help="Forms completed vs management target (70, 50, 100)",
                format="%.1f%%"
            )

        st.dataframe(
            sorted_df,
            column_config=column_configuration,
            width="stretch",
            hide_index=True
        )

        fig_rank = px.bar(
            sorted_df,
            x='NAME',
            y='Overall Score',
            color='Performance Tier',
            title=f"Employee Score Distribution ({sort_order})",
            category_orders={"NAME": sorted_df['NAME'].tolist()}
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
            
            # Displays existing metrics + new target speed add-ons
            st.write(f"- **Total Tasks Handled:** {emp_row['Total Tasks']}")
            if 'Total Forms' in emp_row:
                st.write(f"- **Total Forms Completed:** {emp_row['Total Forms']}")
            if 'Target' in emp_row:
                st.write(f"- **Daily Target Quota:** {emp_row['Target']}")
            if 'Speed Rate (%)' in emp_row:
                st.write(f"- **Speed vs Target:** {emp_row['Speed Rate (%)']:.1f}%")
            
            st.write(f"- **Completed Tasks:** {emp_row['Completed Tasks']}")
            st.write(f"- **Pending Tasks:** {emp_row['Pending Tasks']}")
            st.write(f"- **Completion Rate:** {emp_row['Completion Rate (%)']:.1f}%")
            st.write(f"- **High-Complexity Tasks:** {emp_row['Complex Tasks']}")
            st.write(f"- **Schools Covered:** {emp_row['Schools Serviced']}")

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
        st.subheader("📦 Bulk PDF Export for ALL Staff Members")
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