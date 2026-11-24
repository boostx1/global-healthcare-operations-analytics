-- =============================================================================
-- Global Healthcare Operations & Medical Tourism Analytics
-- File: sql/01_schema.sql
-- Purpose: Normalized Star-Schema Relational Data Model (SQLite / ANSI SQL)
-- Governance: De-identified patient tokens only (zero PII; HIPAA/GDPR-safe)
-- =============================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS etl_data_quality_audit;
DROP TABLE IF EXISTS fact_country_health_indicators;
DROP TABLE IF EXISTS fact_billing;
DROP TABLE IF EXISTS fact_encounters;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_procedure;
DROP TABLE IF EXISTS dim_hospital;
DROP TABLE IF EXISTS dim_country;

-- -----------------------------------------------------------------------------
-- Dimension: Countries (Destination Hubs & Patient Origin Markets)
-- -----------------------------------------------------------------------------
CREATE TABLE dim_country (
    country_code          TEXT PRIMARY KEY,
    country_name          TEXT NOT NULL UNIQUE,
    region                TEXT NOT NULL,
    income_group          TEXT NOT NULL,
    health_system_model   TEXT NOT NULL,
    regulatory_framework  TEXT NOT NULL,
    is_major_destination  INTEGER NOT NULL CHECK (is_major_destination IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- Dimension: International Partner Hospitals
-- -----------------------------------------------------------------------------
CREATE TABLE dim_hospital (
    hospital_id             TEXT PRIMARY KEY,
    hospital_name           TEXT NOT NULL,
    city                    TEXT NOT NULL,
    country_code            TEXT NOT NULL,
    hospital_tier           TEXT NOT NULL CHECK (hospital_tier IN ('Quaternary', 'Tertiary', 'Specialty Center')),
    jci_accredited          INTEGER NOT NULL CHECK (jci_accredited IN (0, 1)),
    licensed_beds           INTEGER NOT NULL CHECK (licensed_beds > 0),
    avg_bed_occupancy_pct   REAL NOT NULL CHECK (avg_bed_occupancy_pct BETWEEN 0 AND 100),
    intl_patient_desk       INTEGER NOT NULL CHECK (intl_patient_desk IN (0, 1)),
    languages_supported     TEXT NOT NULL,
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code)
);

-- -----------------------------------------------------------------------------
-- Dimension: Clinical Procedures & Specialties
-- -----------------------------------------------------------------------------
CREATE TABLE dim_procedure (
    procedure_code            TEXT PRIMARY KEY,
    procedure_name            TEXT NOT NULL,
    specialty                 TEXT NOT NULL,
    clinical_complexity_score INTEGER NOT NULL CHECK (clinical_complexity_score BETWEEN 1 AND 5),
    benchmark_los_days        REAL NOT NULL CHECK (benchmark_los_days >= 0),
    us_benchmark_cost_usd     REAL NOT NULL CHECK (us_benchmark_cost_usd > 0),
    eu_benchmark_cost_usd     REAL NOT NULL CHECK (eu_benchmark_cost_usd > 0),
    gcc_benchmark_cost_usd    REAL NOT NULL CHECK (gcc_benchmark_cost_usd > 0)
);

-- -----------------------------------------------------------------------------
-- Dimension: De-Identified Synthetic Patient Cohort (Zero PII)
-- -----------------------------------------------------------------------------
CREATE TABLE dim_patient (
    patient_token          TEXT PRIMARY KEY,
    origin_country_code    TEXT NOT NULL,
    age_band               TEXT NOT NULL CHECK (age_band IN ('18-34', '35-49', '50-64', '65-74', '75+')),
    sex_at_birth           TEXT NOT NULL CHECK (sex_at_birth IN ('F', 'M')),
    comorbidity_index      INTEGER NOT NULL CHECK (comorbidity_index BETWEEN 0 AND 5),
    payer_type             TEXT NOT NULL CHECK (payer_type IN ('Self-Pay', 'Private International', 'Employer Sponsored', 'Public Cross-Border')),
    FOREIGN KEY (origin_country_code) REFERENCES dim_country(country_code)
);

-- -----------------------------------------------------------------------------
-- Fact: Clinical & Operational Encounters
-- -----------------------------------------------------------------------------
CREATE TABLE fact_encounters (
    encounter_id             TEXT PRIMARY KEY,
    patient_token            TEXT NOT NULL,
    hospital_id              TEXT NOT NULL,
    procedure_code           TEXT NOT NULL,
    is_medical_tourist       INTEGER NOT NULL CHECK (is_medical_tourist IN (0, 1)),
    referral_channel         TEXT NOT NULL,
    admission_date           TEXT NOT NULL,
    discharge_date           TEXT NOT NULL,
    admission_year           INTEGER NOT NULL,
    admission_month          TEXT NOT NULL,
    wait_time_days           INTEGER NOT NULL CHECK (wait_time_days >= 0),
    length_of_stay_days      INTEGER NOT NULL CHECK (length_of_stay_days >= 0),
    complication_flag        INTEGER NOT NULL CHECK (complication_flag IN (0, 1)),
    readmission_30d_flag     INTEGER NOT NULL CHECK (readmission_30d_flag IN (0, 1)),
    clinical_outcome_score   REAL NOT NULL CHECK (clinical_outcome_score BETWEEN 0 AND 100),
    patient_satisfaction     REAL CHECK (patient_satisfaction BETWEEN 1.0 AND 5.0),
    satisfaction_imputed     INTEGER NOT NULL DEFAULT 0 CHECK (satisfaction_imputed IN (0, 1)),
    FOREIGN KEY (patient_token) REFERENCES dim_patient(patient_token),
    FOREIGN KEY (hospital_id) REFERENCES dim_hospital(hospital_id),
    FOREIGN KEY (procedure_code) REFERENCES dim_procedure(procedure_code)
);

-- -----------------------------------------------------------------------------
-- Fact: Financial Transparency, Costs & Cross-Border Savings
-- -----------------------------------------------------------------------------
CREATE TABLE fact_billing (
    billing_id                  TEXT PRIMARY KEY,
    encounter_id                TEXT NOT NULL UNIQUE,
    procedure_cost_usd          REAL NOT NULL CHECK (procedure_cost_usd > 0),
    travel_logistics_usd        REAL NOT NULL CHECK (travel_logistics_usd >= 0),
    total_episode_cost_usd      REAL NOT NULL CHECK (total_episode_cost_usd > 0),
    home_benchmark_cost_usd     REAL NOT NULL CHECK (home_benchmark_cost_usd > 0),
    net_savings_usd             REAL NOT NULL,
    net_savings_pct             REAL NOT NULL,
    out_of_pocket_share_pct     REAL NOT NULL CHECK (out_of_pocket_share_pct BETWEEN 0 AND 100),
    billing_status              TEXT NOT NULL CHECK (billing_status IN ('Settled', 'Insurance Pending', 'Audit Review')),
    FOREIGN KEY (encounter_id) REFERENCES fact_encounters(encounter_id)
);

-- -----------------------------------------------------------------------------
-- Fact: Real-World Macro Health Indicators (World Bank Open Data API v2)
-- -----------------------------------------------------------------------------
CREATE TABLE fact_country_health_indicators (
    country_code    TEXT NOT NULL,
    year            INTEGER NOT NULL,
    indicator_code  TEXT NOT NULL,
    indicator_name  TEXT NOT NULL,
    value           REAL,
    PRIMARY KEY (country_code, year, indicator_code),
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code)
);

-- -----------------------------------------------------------------------------
-- Governance: Automated ETL Data Quality Audit Trail
-- -----------------------------------------------------------------------------
CREATE TABLE etl_data_quality_audit (
    audit_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp_utc TEXT NOT NULL,
    dataset_name      TEXT NOT NULL,
    check_name        TEXT NOT NULL,
    rows_evaluated    INTEGER NOT NULL,
    rows_flagged      INTEGER NOT NULL,
    action_taken      TEXT NOT NULL,
    severity          TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'QUARANTINE'))
);

-- -----------------------------------------------------------------------------
-- Performance Indexes for Analytical Queries & BI Joins
-- -----------------------------------------------------------------------------
CREATE INDEX idx_encounters_hospital ON fact_encounters(hospital_id);
CREATE INDEX idx_encounters_procedure ON fact_encounters(procedure_code);
CREATE INDEX idx_encounters_patient ON fact_encounters(patient_token);
CREATE INDEX idx_encounters_month ON fact_encounters(admission_month);
CREATE INDEX idx_billing_encounter ON fact_billing(encounter_id);
CREATE INDEX idx_wb_country_year ON fact_country_health_indicators(country_code, year);
