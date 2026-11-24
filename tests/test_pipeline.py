"""Automated verification tests for the Healthcare Operations & Medical Tourism pipeline."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "healthcare_ops.db"
REPORTS_DIR = BASE_DIR / "reports"
FIG_DIR = REPORTS_DIR / "figures"
DASHBOARD_HTML = BASE_DIR / "dashboard" / "index.html"
XLSX_PATH = REPORTS_DIR / "Healthcare_Operations_Analytics_Workbook.xlsx"


def test_sqlite_schema_and_fk_integrity() -> None:
    assert DB_PATH.exists(), "SQLite warehouse database not found."
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        assert fk_violations == [], f"Foreign key violations: {fk_violations}"

        enc_count = conn.execute("SELECT COUNT(*) FROM fact_encounters").fetchone()[0]
        bill_count = conn.execute("SELECT COUNT(*) FROM fact_billing").fetchone()[0]
        wb_count = conn.execute("SELECT COUNT(*) FROM fact_country_health_indicators").fetchone()[0]
        assert enc_count == 6000
        assert bill_count == 6000
        assert wb_count == 640
    finally:
        conn.close()


def test_etl_eliminated_invalid_records() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        bad_los = conn.execute("SELECT COUNT(*) FROM fact_encounters WHERE length_of_stay_days < 0").fetchone()[0]
        bad_sat = conn.execute("SELECT COUNT(*) FROM fact_encounters WHERE patient_satisfaction < 1 OR patient_satisfaction > 5").fetchone()[0]
        bad_cost = conn.execute("SELECT COUNT(*) FROM fact_billing WHERE procedure_cost_usd <= 0").fetchone()[0]
        audit_cnt = conn.execute("SELECT COUNT(*) FROM etl_data_quality_audit").fetchone()[0]
        assert bad_los == 0
        assert bad_sat == 0
        assert bad_cost == 0
        assert audit_cnt >= 10
    finally:
        conn.close()


def test_analytical_views_return_expected_rows() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        assert conn.execute("SELECT COUNT(*) FROM vw_hospital_scorecard").fetchone()[0] == 24
        assert conn.execute("SELECT COUNT(*) FROM vw_jci_accreditation_impact").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM vw_monthly_operations_kpi").fetchone()[0] == 36
        assert conn.execute("SELECT COUNT(*) FROM vw_country_macro_vs_ops").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM vw_medical_tourism_corridors").fetchone()[0] >= 10
    finally:
        conn.close()


def test_statistical_outputs_valid() -> None:
    stats_path = REPORTS_DIR / "statistical_results.json"
    assert stats_path.exists()
    data = json.loads(stats_path.read_text(encoding="utf-8"))
    assert data["jci_readmission_test"]["significant_05"] is True
    assert data["jci_complication_test"]["significant_05"] is True
    assert 0.5 < data["ols_patient_satisfaction"]["r_squared"] < 1.0
    assert 0.7 < data["ols_length_of_stay"]["r_squared"] < 1.0
    assert len(data["hospital_bootstrap_ci"]) == 24


def test_all_figures_excel_and_dashboard_exist() -> None:
    expected_figs = [
        "01_medical_tourism_corridors_savings.png",
        "02_hospital_quality_vs_cost_quadrant.png",
        "03_jci_clinical_outcomes_ci.png",
        "04_monthly_volume_readmission_trends.png",
        "05_worldbank_macro_benchmarks.png",
        "06_regression_drivers_satisfaction.png",
    ]
    for name in expected_figs:
        p = FIG_DIR / name
        assert p.exists() and p.stat().st_size > 20_000, f"Missing or tiny chart: {name}"

    assert XLSX_PATH.exists()
    wb = load_workbook(XLSX_PATH, data_only=False)
    assert set(wb.sheetnames) == {
        "Executive_Summary",
        "Hospital_Scorecard",
        "Medical_Tourism_Corridors",
        "Statistical_Tests",
        "Data_Quality_Audit",
    }
    # Verify live Excel formulas are embedded (not hardcoded values)
    assert str(wb["Executive_Summary"]["C5"].value).startswith("=SUM(")
    assert str(wb["Hospital_Scorecard"]["Q2"].value).startswith("=ROUND(")
    assert str(wb["Medical_Tourism_Corridors"]["F2"].value).startswith("=D2-E2")

    assert DASHBOARD_HTML.exists()
    html_text = DASHBOARD_HTML.read_text(encoding="utf-8")
    assert "Global Healthcare Operations" in html_text
    assert "vw_hospital_scorecard" not in html_text  # Real JSON payload injected
    assert "Al Noor Gulf Medical Center" in html_text
