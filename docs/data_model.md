# Relational Data Model & BI Integration Guide

## 1. Star-Schema Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    dim_country ||--o{ dim_hospital : "hosts"
    dim_country ||--o{ dim_patient : "patient_origin"
    dim_country ||--o{ fact_country_health_indicators : "worldbank_macro"
    dim_hospital ||--o{ fact_encounters : "treats"
    dim_procedure ||--o{ fact_encounters : "performs"
    dim_patient ||--o{ fact_encounters : "undergoes"
    fact_encounters ||--|| fact_billing : "billed_as"

    dim_country {
        TEXT country_code PK
        TEXT country_name
        TEXT region
        TEXT income_group
        TEXT health_system_model
        TEXT regulatory_framework
        INTEGER is_major_destination
    }

    dim_hospital {
        TEXT hospital_id PK
        TEXT hospital_name
        TEXT city
        TEXT country_code FK
        TEXT hospital_tier
        INTEGER jci_accredited
        INTEGER licensed_beds
        REAL avg_bed_occupancy_pct
        INTEGER intl_patient_desk
        TEXT languages_supported
    }

    dim_procedure {
        TEXT procedure_code PK
        TEXT procedure_name
        TEXT specialty
        INTEGER clinical_complexity_score
        REAL benchmark_los_days
        REAL us_benchmark_cost_usd
        REAL eu_benchmark_cost_usd
        REAL gcc_benchmark_cost_usd
    }

    dim_patient {
        TEXT patient_token PK
        TEXT origin_country_code FK
        TEXT age_band
        TEXT sex_at_birth
        INTEGER comorbidity_index
        TEXT payer_type
    }

    fact_encounters {
        TEXT encounter_id PK
        TEXT patient_token FK
        TEXT hospital_id FK
        TEXT procedure_code FK
        INTEGER is_medical_tourist
        TEXT referral_channel
        TEXT admission_date
        TEXT discharge_date
        INTEGER wait_time_days
        INTEGER length_of_stay_days
        INTEGER complication_flag
        INTEGER readmission_30d_flag
        REAL clinical_outcome_score
        REAL patient_satisfaction
        INTEGER satisfaction_imputed
    }

    fact_billing {
        TEXT billing_id PK
        TEXT encounter_id FK
        REAL procedure_cost_usd
        REAL travel_logistics_usd
        REAL total_episode_cost_usd
        REAL home_benchmark_cost_usd
        REAL net_savings_usd
        REAL net_savings_pct
        REAL out_of_pocket_share_pct
        TEXT billing_status
    }

    fact_country_health_indicators {
        TEXT country_code PK
        INTEGER year PK
        TEXT indicator_code PK
        TEXT indicator_name
        REAL value
    }

    etl_data_quality_audit {
        INTEGER audit_id PK
        TEXT run_timestamp_utc
        TEXT dataset_name
        TEXT check_name
        INTEGER rows_evaluated
        INTEGER rows_flagged
        TEXT action_taken
        TEXT severity
    }
```

## 2. Table Grains & Modeling Decisions

| Table / View | Grain | Primary Key | Notes |
| --- | --- | --- | --- |
| `dim_country` | 1 row per ISO-3 nation | `country_code` | Covers 8 destination hubs and origin markets (`ARE, SWE, DEU, TUR, THA, IND, SGP, USA`). |
| `dim_hospital` | 1 row per partner facility | `hospital_id` | 24 hospitals across Quaternary, Tertiary, and Specialty tiers; tracks JCI accreditation & capacity. |
| `dim_procedure` | 1 row per standardized procedure | `procedure_code` | 12 high-volume cross-border procedures with complexity ratings and regional benchmark costs. |
| `dim_patient` | 1 row per de-identified patient | `patient_token` | SHA-256 salted synthetic token (`PT-...`); age stored as bands only (zero PII). |
| `fact_encounters` | 1 row per clinical episode | `encounter_id` | 6,000 validated encounters (2023–2025). Includes `satisfaction_imputed` flag for analytical transparency. |
| `fact_billing` | 1 row per encounter invoice | `billing_id` | 1:1 with `fact_encounters` via unique `encounter_id`; separates clinical vs. travel logistics costs. |
| `fact_country_health_indicators` | 1 row per country-year-indicator | `(country_code, year, indicator_code)` | 640 live observations from World Bank Open Data API v2 (2015–2024). Reporting-lag NULLs preserved. |
| `etl_data_quality_audit` | 1 row per automated ETL check | `audit_id` | Full lineage of deduplication, standardization, quarantine counts, and imputation. |

## 3. Power BI / Tableau Quick-Connect Setup

All normalized dimension tables, fact tables, and pre-aggregated views are exported cleanly to `data/bi_exports/`:

1. **Power BI Desktop:** `Get Data -> Folder -> data/bi_exports/` (or import the 4 `dim_*.csv` + 3 `fact_*.csv` files directly). Relate `country_code`, `hospital_id`, `procedure_code`, `patient_token`, and `encounter_id` in Model View using the Star Schema above.
2. **Tableau Desktop / Public:** Connect to `fact_encounters.csv` and drag `fact_billing.csv`, `dim_hospital.csv`, `dim_procedure.csv`, `dim_patient.csv`, and `dim_country.csv` into the logical layer on their matching primary/foreign keys.
3. **Excel:** Open `reports/Healthcare_Operations_Analytics_Workbook.xlsx` directly — all KPI rollups, composite scores, ranks, and corridor savings use live Excel formulas.
