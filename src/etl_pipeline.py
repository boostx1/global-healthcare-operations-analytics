"""Multi-source ETL pipeline: cleans, standardizes, validates, audits, and loads
synthetic clinical operations feeds + real World Bank Open Data into SQLite,
then exports BI-ready Star-Schema CSVs for Power BI / Tableau / Excel.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"
BI_DIR = BASE_DIR / "data" / "bi_exports"
SQL_DIR = BASE_DIR / "sql"
DB_PATH = PROC_DIR / "healthcare_ops.db"

COUNTRY_STANDARDIZATION = {
    "are": "ARE", "uae": "ARE", "u.a.e.": "ARE", "united arab emirates": "ARE",
    "swe": "SWE", "sweden": "SWE", "se": "SWE",
    "deu": "DEU", "germany": "DEU", "de": "DEU",
    "tur": "TUR", "turkey": "TUR", "turkiye": "TUR", "türkiye": "TUR",
    "tha": "THA", "thailand": "THA", "th": "THA",
    "ind": "IND", "india": "IND", "in": "IND",
    "sgp": "SGP", "singapore": "SGP", "sg": "SGP",
    "usa": "USA", "us": "USA", "united states": "USA",
}


def standardize_country(series: pd.Series) -> tuple[pd.Series, int]:
    cleaned = series.astype(str).str.strip()
    mapped = cleaned.str.lower().map(COUNTRY_STANDARDIZATION)
    n_changed = int((cleaned != mapped).sum())
    return mapped, n_changed


def parse_mixed_date(val: str) -> str:
    val = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {val}")


def run_etl() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    BI_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.now(timezone.utc).isoformat()
    audit_rows: list[tuple] = []
    quarantine_frames: list[pd.DataFrame] = []

    def log_audit(dataset: str, check: str, evaluated: int, flagged: int, action: str, severity: str) -> None:
        audit_rows.append((run_ts, dataset, check, int(evaluated), int(flagged), action, severity))

    # 1. Load reference dimensions
    df_countries = pd.read_csv(RAW_DIR / "raw_countries.csv")
    df_procedures = pd.read_csv(RAW_DIR / "raw_procedures.csv")

    # 2. Clean raw_hospitals
    df_hospitals = pd.read_csv(RAW_DIR / "raw_hospitals.csv")
    df_hospitals["country_code"], n_hosp_std = standardize_country(df_hospitals["country_raw"])
    log_audit(
        "raw_hospitals", "Country alias standardization (ISO-3)",
        len(df_hospitals), n_hosp_std, "Mapped country variants to ISO-3 codes", "INFO"
    )
    df_hospitals = df_hospitals.drop(columns=["country_raw"])

    # 3. Clean raw_patients
    df_patients = pd.read_csv(RAW_DIR / "raw_patients.csv")
    df_patients["origin_country_code"], n_pt_std = standardize_country(df_patients["origin_country_raw"])
    log_audit(
        "raw_patients", "Origin country alias standardization (ISO-3)",
        len(df_patients), n_pt_std, "Mapped origin country variants to ISO-3 codes", "INFO"
    )
    df_patients = df_patients.drop(columns=["origin_country_raw"])

    # 4. Clean raw_encounters
    df_enc_raw = pd.read_csv(RAW_DIR / "raw_encounters.csv")
    n_enc_in = len(df_enc_raw)

    # 4a. Deduplicate encounter_id
    dup_mask = df_enc_raw.duplicated(subset=["encounter_id"], keep="first")
    n_dups = int(dup_mask.sum())
    if n_dups > 0:
        q = df_enc_raw[dup_mask].copy()
        q["quarantine_reason"] = "Duplicate encounter_id"
        quarantine_frames.append(q)
    df_enc = df_enc_raw[~dup_mask].copy()
    log_audit(
        "raw_encounters", "Duplicate encounter_id detection",
        n_enc_in, n_dups, "Removed duplicate rows and logged to quarantine", "QUARANTINE"
    )

    # 4b. Standardize mixed date formats
    mixed_date_mask = df_enc["admission_date"].astype(str).str.contains("/", regex=False)
    n_mixed_dates = int(mixed_date_mask.sum())
    df_enc["admission_date"] = df_enc["admission_date"].apply(parse_mixed_date)
    df_enc["discharge_date"] = df_enc["discharge_date"].apply(parse_mixed_date)
    log_audit(
        "raw_encounters", "Mixed date format standardization (DD/MM/YYYY -> ISO-8601)",
        len(df_enc), n_mixed_dates, "Converted non-ISO dates to YYYY-MM-DD", "INFO"
    )

    # 4c. Referential integrity check against valid hospital_id / patient_token / procedure_code
    valid_hosps = set(df_hospitals["hospital_id"])
    valid_pts = set(df_patients["patient_token"])
    valid_procs = set(df_procedures["procedure_code"])
    orphan_mask = (
        ~df_enc["hospital_id"].isin(valid_hosps)
        | ~df_enc["patient_token"].isin(valid_pts)
        | ~df_enc["procedure_code"].isin(valid_procs)
    )
    n_orphans = int(orphan_mask.sum())
    if n_orphans > 0:
        q = df_enc[orphan_mask].copy()
        q["quarantine_reason"] = "Foreign key violation (unknown hospital/patient/procedure)"
        quarantine_frames.append(q)
    df_enc = df_enc[~orphan_mask].copy()
    log_audit(
        "raw_encounters", "Foreign key referential integrity check",
        len(df_enc) + n_orphans, n_orphans, "Quarantined orphan records prior to warehouse load", "QUARANTINE"
    )

    # 4d. Domain range validation (LOS >= 0, wait >= 0, outcome 0-100, satisfaction 1-5 when present)
    df_enc["patient_satisfaction"] = pd.to_numeric(df_enc["patient_satisfaction"], errors="coerce")
    invalid_range_mask = (
        (df_enc["length_of_stay_days"] < 0)
        | (df_enc["wait_time_days"] < 0)
        | (df_enc["clinical_outcome_score"] < 0)
        | (df_enc["clinical_outcome_score"] > 100)
        | (df_enc["patient_satisfaction"].notna() & ((df_enc["patient_satisfaction"] < 1.0) | (df_enc["patient_satisfaction"] > 5.0)))
    )
    n_invalid = int(invalid_range_mask.sum())
    if n_invalid > 0:
        q = df_enc[invalid_range_mask].copy()
        q["quarantine_reason"] = "Out-of-range clinical/satisfaction value (e.g. negative LOS or satisfaction > 5)"
        quarantine_frames.append(q)
    df_enc = df_enc[~invalid_range_mask].copy()
    log_audit(
        "raw_encounters", "Clinical & operational domain range validation",
        len(df_enc) + n_invalid, n_invalid, "Quarantined records violating clinical/bounds rules", "QUARANTINE"
    )

    # 4e. Missing satisfaction imputation (hospital-level median, transparently flagged)
    missing_sat_mask = df_enc["patient_satisfaction"].isna()
    n_missing_sat = int(missing_sat_mask.sum())
    hosp_medians = df_enc.groupby("hospital_id")["patient_satisfaction"].transform("median")
    df_enc["satisfaction_imputed"] = missing_sat_mask.astype(int)
    df_enc["patient_satisfaction"] = df_enc["patient_satisfaction"].fillna(hosp_medians).round(2)
    log_audit(
        "raw_encounters", "Missing patient satisfaction survey handling",
        len(df_enc), n_missing_sat, "Imputed with hospital median & set satisfaction_imputed=1 flag", "WARNING"
    )

    # Derive time hierarchy columns
    df_enc["admission_year"] = df_enc["admission_date"].str.slice(0, 4).astype(int)
    df_enc["admission_month"] = df_enc["admission_date"].str.slice(0, 7)

    # 5. Clean raw_billing
    df_bill_raw = pd.read_csv(RAW_DIR / "raw_billing.csv")
    n_bill_in = len(df_bill_raw)
    df_bill = df_bill_raw.drop_duplicates(subset=["encounter_id"], keep="first").copy()
    n_bill_dups = n_bill_in - len(df_bill)
    log_audit(
        "raw_billing", "Duplicate encounter billing deduplication",
        n_bill_in, n_bill_dups, "Retained unique encounter billing rows", "QUARANTINE"
    )

    valid_enc_ids = set(df_enc["encounter_id"])
    bill_invalid_mask = (
        ~df_bill["encounter_id"].isin(valid_enc_ids)
        | (df_bill["procedure_cost_usd"] <= 0)
        | (df_bill["total_episode_cost_usd"] <= 0)
        | (df_bill["travel_logistics_usd"] < 0)
    )
    n_bill_bad = int(bill_invalid_mask.sum())
    df_bill = df_bill[~bill_invalid_mask].copy()
    log_audit(
        "raw_billing", "Billing validity & encounter FK check",
        len(df_bill) + n_bill_bad, n_bill_bad, "Removed negative/unlinked billing records", "QUARANTINE"
    )

    # Compute transparent net savings metrics
    df_bill["net_savings_usd"] = (df_bill["home_benchmark_cost_usd"] - df_bill["total_episode_cost_usd"]).round(2)
    df_bill["net_savings_pct"] = (
        100.0 * df_bill["net_savings_usd"] / df_bill["home_benchmark_cost_usd"]
    ).round(2)

    # 6. Load real World Bank Open Data CSV & audit missingness (preserve NULLs truthfully!)
    df_wb = pd.read_csv(RAW_DIR / "worldbank_health_indicators.csv")
    n_wb_null = int(df_wb["value"].isna().sum())
    log_audit(
        "worldbank_health_indicators", "Official World Bank API missingness audit (2015-2024)",
        len(df_wb), n_wb_null, "Preserved NULL reporting lags truthfully; views use latest non-null observation", "WARNING"
    )

    # Save quarantine log
    if quarantine_frames:
        df_quarantine = pd.concat(quarantine_frames, ignore_index=True)
        df_quarantine.to_csv(PROC_DIR / "quarantined_records.csv", index=False)

    # 7. Build SQLite warehouse from schema & views
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript((SQL_DIR / "01_schema.sql").read_text(encoding="utf-8"))

        df_countries.to_sql("dim_country", conn, if_exists="append", index=False)
        df_hospitals.to_sql("dim_hospital", conn, if_exists="append", index=False)
        df_procedures.to_sql("dim_procedure", conn, if_exists="append", index=False)
        df_patients.to_sql("dim_patient", conn, if_exists="append", index=False)

        enc_cols = [
            "encounter_id", "patient_token", "hospital_id", "procedure_code",
            "is_medical_tourist", "referral_channel", "admission_date", "discharge_date",
            "admission_year", "admission_month", "wait_time_days", "length_of_stay_days",
            "complication_flag", "readmission_30d_flag", "clinical_outcome_score",
            "patient_satisfaction", "satisfaction_imputed",
        ]
        df_enc[enc_cols].to_sql("fact_encounters", conn, if_exists="append", index=False)

        bill_cols = [
            "billing_id", "encounter_id", "procedure_cost_usd", "travel_logistics_usd",
            "total_episode_cost_usd", "home_benchmark_cost_usd", "net_savings_usd",
            "net_savings_pct", "out_of_pocket_share_pct", "billing_status",
        ]
        df_bill[bill_cols].to_sql("fact_billing", conn, if_exists="append", index=False)

        wb_cols = ["country_code", "year", "indicator_code", "indicator_name", "value"]
        df_wb[wb_cols].to_sql("fact_country_health_indicators", conn, if_exists="append", index=False)

        conn.executemany(
            """
            INSERT INTO etl_data_quality_audit
            (run_timestamp_utc, dataset_name, check_name, rows_evaluated, rows_flagged, action_taken, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            audit_rows,
        )

        # Create analytical views
        conn.executescript((SQL_DIR / "02_views.sql").read_text(encoding="utf-8"))
        conn.commit()

        # Verify zero foreign key violations
        fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_errors:
            raise RuntimeError(f"Foreign key violations detected: {fk_errors[:5]}")

        # 8. Export clean Star-Schema tables & views for Power BI / Tableau
        export_objects = [
            "dim_country",
            "dim_hospital",
            "dim_procedure",
            "dim_patient",
            "fact_encounters",
            "fact_billing",
            "fact_country_health_indicators",
            "etl_data_quality_audit",
            "vw_hospital_scorecard",
            "vw_medical_tourism_corridors",
            "vw_jci_accreditation_impact",
            "vw_monthly_operations_kpi",
            "vw_country_macro_vs_ops",
        ]
        for obj in export_objects:
            pd.read_sql_query(f"SELECT * FROM {obj}", conn).to_csv(BI_DIR / f"{obj}.csv", index=False)

        print(
            f"ETL completed cleanly -> {DB_PATH}\n"
            f"  Clean encounters loaded: {len(df_enc):,} | Clean billing loaded: {len(df_bill):,}\n"
            f"  Real World Bank rows loaded: {len(df_wb):,} | Audit checks logged: {len(audit_rows)}\n"
            f"  Exported {len(export_objects)} BI-ready CSV tables/views to {BI_DIR}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    run_etl()
