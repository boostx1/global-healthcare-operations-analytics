"""Build a formatted, multi-sheet executive Excel workbook with live formulas,
conditional formatting, and native openpyxl charts for non-technical stakeholders
and healthcare partner teams.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "healthcare_ops.db"
REPORTS_DIR = BASE_DIR / "reports"
OUT_XLSX = REPORTS_DIR / "Healthcare_Operations_Analytics_Workbook.xlsx"

NAVY_FILL = PatternFill("solid", fgColor="0F3D5E")
TEAL_FILL = PatternFill("solid", fgColor="0D9488")
SUB_FILL = PatternFill("solid", fgColor="E2E8F0")
ALT_FILL = PatternFill("solid", fgColor="F8FAFC")
CARD_FILL = PatternFill("solid", fgColor="F1F5F9")

WHITE_BOLD = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=15, bold=True, color="0F3D5E")
SUBTITLE_FONT = Font(name="Calibri", size=10, italic=True, color="475569")
SEC_FONT = Font(name="Calibri", size=11, bold=True, color="0F3D5E")
BODY_FONT = Font(name="Calibri", size=10, color="1E293B")
BOLD_FONT = Font(name="Calibri", size=10, bold=True, color="0F3D5E")
KPI_NUM_FONT = Font(name="Calibri", size=16, bold=True, color="0D9488")

THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


def autofit_columns(ws, min_w: int = 11, max_w: int = 44) -> None:
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = "" if cell.value is None else str(cell.value)
            if val.startswith("="):
                val = "1234567890"
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = max(min_w, min(max_len + 3, max_w))


def style_table_header(ws, row_idx: int, n_cols: int) -> None:
    ws.row_dimensions[row_idx].height = 26
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row_idx, column=c)
        cell.fill = NAVY_FILL
        cell.font = WHITE_BOLD
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def build_workbook() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        df_hosp = pd.read_sql_query("SELECT * FROM vw_hospital_scorecard ORDER BY quality_rank", conn)
        df_corr = pd.read_sql_query("SELECT * FROM vw_medical_tourism_corridors", conn)
        df_wb = pd.read_sql_query("SELECT * FROM vw_country_macro_vs_ops", conn)
        df_audit = pd.read_sql_query("SELECT * FROM etl_data_quality_audit ORDER BY audit_id", conn)
    finally:
        conn.close()

    df_stats = pd.read_csv(REPORTS_DIR / "statistical_summary.csv")

    wb = Workbook()

    # =========================================================================
    # Sheet 1: Executive_Summary (Live formula KPIs + Country rollup + Chart)
    # =========================================================================
    ws_exec = wb.active
    ws_exec.title = "Executive_Summary"
    ws_exec.views.sheetView[0].showGridLines = True

    ws_exec["A1"] = "Global Healthcare Operations & Medical Tourism Analytics — Executive Summary"
    ws_exec["A1"].font = TITLE_FONT
    ws_exec["A2"] = "Live formula-driven KPI dashboard built on SQLite Star Schema + Real World Bank Open Data API"
    ws_exec["A2"].font = SUBTITLE_FONT

    n_h = len(df_hosp)
    h_end = n_h + 1

    kpi_cards = [
        ("Total Partner Hospitals", f"=COUNTA(Hospital_Scorecard!A2:A{h_end})", "#,##0"),
        ("JCI Accredited Hospitals", f'=COUNTIF(Hospital_Scorecard!F2:F{h_end},"Yes")', "#,##0"),
        ("Total Clean Encounters", f"=SUM(Hospital_Scorecard!I2:I{h_end})", "#,##0"),
        ("Intl. Medical Tourists", f"=SUM(Hospital_Scorecard!J2:J{h_end})", "#,##0"),
        ("Avg Network Quality Score", f"=AVERAGE(Hospital_Scorecard!Q2:Q{h_end})", "0.00"),
        ("Avg 30-Day Readmission %", f"=AVERAGE(Hospital_Scorecard!L2:L{h_end})/100", "0.00%"),
    ]

    for idx, (label, formula, num_fmt) in enumerate(kpi_cards):
        col = idx + 1
        c_lbl = ws_exec.cell(row=4, column=col, value=label)
        c_lbl.fill = SUB_FILL
        c_lbl.font = BOLD_FONT
        c_lbl.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c_lbl.border = THIN_BORDER

        c_val = ws_exec.cell(row=5, column=col, value=formula)
        c_val.fill = CARD_FILL
        c_val.font = KPI_NUM_FONT
        c_val.number_format = num_fmt
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        c_val.border = THIN_BORDER
    ws_exec.row_dimensions[4].height = 24
    ws_exec.row_dimensions[5].height = 30

    # Country Benchmark Table (World Bank Real Data + Live Formula Operational Rollups)
    ws_exec["A7"] = "Country-Level Macro Benchmarks (World Bank API) & Live Hospital Network Rollups"
    ws_exec["A7"].font = SEC_FONT

    exec_headers = [
        "Country", "Region", "WB Health Spend/Capita ($)", "WB Out-of-Pocket (%)",
        "WB Life Expectancy (Yrs)", "WB Beds / 1,000", "Partner Hospitals (Formula)",
        "Network Encounters (Formula)", "Avg Procedure Cost (Formula)", "Avg Quality Score (Formula)"
    ]
    for c_i, h in enumerate(exec_headers, start=1):
        ws_exec.cell(row=8, column=c_i, value=h)
    style_table_header(ws_exec, 8, len(exec_headers))

    for r_idx, r in df_wb.reset_index(drop=True).iterrows():
        row_num = 9 + r_idx
        cname = r["country_name"]
        vals = [
            cname,
            r["region"],
            None if pd.isna(r["wb_health_spend_pc_usd"]) else float(r["wb_health_spend_pc_usd"]),
            None if pd.isna(r["wb_oop_pct_spend"]) else float(r["wb_oop_pct_spend"]) / 100.0,
            None if pd.isna(r["wb_life_expectancy"]) else float(r["wb_life_expectancy"]),
            None if pd.isna(r["wb_beds_per_1000"]) else float(r["wb_beds_per_1000"]),
            f'=COUNTIF(Hospital_Scorecard!$D$2:$D${h_end},A{row_num})',
            f'=SUMIF(Hospital_Scorecard!$D$2:$D${h_end},A{row_num},Hospital_Scorecard!$I$2:$I${h_end})',
            f'=AVERAGEIF(Hospital_Scorecard!$D$2:$D${h_end},A{row_num},Hospital_Scorecard!$P$2:$P${h_end})',
            f'=AVERAGEIF(Hospital_Scorecard!$D$2:$D${h_end},A{row_num},Hospital_Scorecard!$Q$2:$Q${h_end})',
        ]
        fmts = ["@", "@", "$#,##0", "0.0%", "0.0", "0.00", "#,##0", "#,##0", "$#,##0", "0.00"]
        for c_i, (val, fmt) in enumerate(zip(vals, fmts), start=1):
            cell = ws_exec.cell(row=row_num, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.number_format = fmt
            cell.border = THIN_BORDER
            if r_idx % 2 == 1:
                cell.fill = ALT_FILL

    # Native Excel Bar Chart: Average Procedure Cost by Destination Country
    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = "Average Partner Procedure Cost by Country (USD)"
    chart.y_axis.title = "USD"
    chart.x_axis.title = "Country"
    data_ref = Reference(ws_exec, min_col=9, min_row=8, max_row=8 + len(df_wb))
    cats_ref = Reference(ws_exec, min_col=1, min_row=9, max_row=8 + len(df_wb))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.legend = None
    chart.width = 18
    chart.height = 10
    ws_exec.add_chart(chart, "A19")

    autofit_columns(ws_exec)

    # =========================================================================
    # Sheet 2: Hospital_Scorecard (Live Composite Score & Rank Formulas)
    # =========================================================================
    ws_hosp = wb.create_sheet("Hospital_Scorecard")
    ws_hosp.freeze_panes = "A2"

    hosp_headers = [
        "Hospital ID", "Hospital Name", "City", "Country", "Tier", "JCI Accredited",
        "Licensed Beds", "Occupancy %", "Total Encounters", "Intl Encounters",
        "Avg Wait (Days)", "Readmission Rate (%)", "Complication Rate (%)",
        "Avg Outcome (0-100)", "Avg Satisfaction (1-5)", "Avg Procedure Cost ($)",
        "Composite Quality Score (Formula)", "Network Rank (Formula)"
    ]
    for c_i, h in enumerate(hosp_headers, start=1):
        ws_hosp.cell(row=1, column=c_i, value=h)
    style_table_header(ws_hosp, 1, len(hosp_headers))

    for idx, r in df_hosp.reset_index(drop=True).iterrows():
        rn = idx + 2
        row_vals = [
            r["hospital_id"],
            r["hospital_name"],
            r["city"],
            r["country_name"],
            r["hospital_tier"],
            "Yes" if int(r["jci_accredited"]) == 1 else "No",
            int(r["licensed_beds"]),
            float(r["avg_bed_occupancy_pct"]) / 100.0,
            int(r["total_encounters"]),
            int(r["intl_encounters"]),
            float(r["avg_wait_days"]),
            float(r["readmission_rate_pct"]),
            float(r["complication_rate_pct"]),
            float(r["avg_clinical_outcome"]),
            float(r["avg_satisfaction"]),
            float(r["avg_procedure_cost_usd"]),
            f"=ROUND(0.35*N{rn}+0.25*MAX(0,100-L{rn}*5)+0.2*MAX(0,100-M{rn}*5)+0.2*(O{rn}*20),2)",
            f"=RANK(Q{rn},$Q$2:$Q${h_end})",
        ]
        fmts = [
            "@", "@", "@", "@", "@", "@",
            "#,##0", "0.0%", "#,##0", "#,##0",
            "0.0", "0.00", "0.00",
            "0.00", "0.00", "$#,##0",
            "0.00", "#,##0",
        ]
        for c_i, (val, fmt) in enumerate(zip(row_vals, fmts), start=1):
            cell = ws_hosp.cell(row=rn, column=c_i, value=val)
            cell.font = BOLD_FONT if c_i in (2, 17, 18) else BODY_FONT
            cell.number_format = fmt
            cell.border = THIN_BORDER
            if idx % 2 == 1:
                cell.fill = ALT_FILL

    ws_hosp.auto_filter.ref = f"A1:R{h_end}"
    ws_hosp.conditional_formatting.add(
        f"Q2:Q{h_end}",
        ColorScaleRule(start_type="min", start_color="FECACA", mid_type="percentile", mid_value=50, mid_color="FEF08A", end_type="max", end_color="A7F3D0"),
    )
    autofit_columns(ws_hosp)

    # =========================================================================
    # Sheet 3: Medical_Tourism_Corridors (Live Net Savings Formulas)
    # =========================================================================
    ws_corr = wb.create_sheet("Medical_Tourism_Corridors")
    ws_corr.freeze_panes = "A2"
    corr_headers = [
        "Origin Country", "Destination Country", "Encounter Volume",
        "Avg Home Cost ($)", "Avg Dest Total Cost ($)",
        "Net Savings $ (Formula)", "Net Savings % (Formula)",
        "Avg Wait (Days)", "Readmission Rate (%)", "Avg Satisfaction"
    ]
    for c_i, h in enumerate(corr_headers, start=1):
        ws_corr.cell(row=1, column=c_i, value=h)
    style_table_header(ws_corr, 1, len(corr_headers))

    for idx, r in df_corr.reset_index(drop=True).iterrows():
        rn = idx + 2
        row_vals = [
            r["origin_country"],
            r["destination_country"],
            int(r["encounter_volume"]),
            float(r["avg_home_cost_usd"]),
            float(r["avg_destination_total_usd"]),
            f"=D{rn}-E{rn}",
            f"=IF(D{rn}>0,(D{rn}-E{rn})/D{rn},0)",
            float(r["avg_wait_days"]),
            float(r["readmission_rate_pct"]) / 100.0,
            float(r["avg_satisfaction"]),
        ]
        fmts = ["@", "@", "#,##0", "$#,##0", "$#,##0", "$#,##0;-$#,##0", "0.0%", "0.0", "0.00%", "0.00"]
        for c_i, (val, fmt) in enumerate(zip(row_vals, fmts), start=1):
            cell = ws_corr.cell(row=rn, column=c_i, value=val)
            cell.font = BODY_FONT
            cell.number_format = fmt
            cell.border = THIN_BORDER
            if idx % 2 == 1:
                cell.fill = ALT_FILL
    ws_corr.auto_filter.ref = f"A1:J{len(df_corr) + 1}"
    autofit_columns(ws_corr)

    # =========================================================================
    # Sheet 4: Statistical_Tests
    # =========================================================================
    ws_st = wb.create_sheet("Statistical_Tests")
    ws_st.freeze_panes = "A2"
    st_headers = ["Test ID", "Research Hypothesis", "Statistical Method", "Test Statistic", "p-value", "Quantitative Finding", "Decision"]
    for c_i, h in enumerate(st_headers, start=1):
        ws_st.cell(row=1, column=c_i, value=h)
    style_table_header(ws_st, 1, len(st_headers))

    for idx, r in df_stats.reset_index(drop=True).iterrows():
        rn = idx + 2
        vals = [r["test_id"], r["hypothesis"], r["method"], r["statistic"], r["p_value"], r["effect_summary"], r["decision"]]
        for c_i, val in enumerate(vals, start=1):
            cell = ws_st.cell(row=rn, column=c_i, value=val)
            cell.font = BOLD_FONT if c_i in (1, 7) else BODY_FONT
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = THIN_BORDER
            if idx % 2 == 1:
                cell.fill = ALT_FILL
        ws_st.row_dimensions[rn].height = 30
    autofit_columns(ws_st, min_w=12, max_w=46)

    # =========================================================================
    # Sheet 5: Data_Quality_Audit
    # =========================================================================
    ws_dq = wb.create_sheet("Data_Quality_Audit")
    ws_dq.freeze_panes = "A2"
    dq_headers = ["Audit ID", "Run Timestamp (UTC)", "Dataset", "Validation Check", "Rows Evaluated", "Rows Flagged", "Action Taken", "Severity"]
    for c_i, h in enumerate(dq_headers, start=1):
        ws_dq.cell(row=1, column=c_i, value=h)
    style_table_header(ws_dq, 1, len(dq_headers))

    for idx, r in df_audit.reset_index(drop=True).iterrows():
        rn = idx + 2
        vals = [
            int(r["audit_id"]), r["run_timestamp_utc"], r["dataset_name"], r["check_name"],
            int(r["rows_evaluated"]), int(r["rows_flagged"]), r["action_taken"], r["severity"]
        ]
        for c_i, val in enumerate(vals, start=1):
            cell = ws_dq.cell(row=rn, column=c_i, value=val)
            cell.font = BOLD_FONT if c_i == 8 else BODY_FONT
            cell.border = THIN_BORDER
            if c_i in (5, 6):
                cell.number_format = "#,##0"
            if idx % 2 == 1:
                cell.fill = ALT_FILL
    autofit_columns(ws_dq, min_w=12, max_w=46)

    wb.save(OUT_XLSX)
    print(f"Built formatted multi-sheet Excel workbook -> {OUT_XLSX}")


if __name__ == "__main__":
    build_workbook()
