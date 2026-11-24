# Healthcare Data Governance & Cross-Border Regulatory Framework

Cross-border healthcare analytics requires combining operational transparency with strict protection of sensitive medical data. This document outlines the privacy, compliance, and data-quality principles implemented in this repository.

## 1. Data Provenance & Transparency

This project combines **two clearly separated data layers**:

1. **Real Public Macro-Health Data (`worldbank_health_indicators.csv`)**
   - Retrieved programmatically from the official **World Bank Open Data API v2** (`SH.MED.BEDS.ZS`, `SH.MED.PHYS.ZS`, `SH.XPD.CHEX.PC.CD`, `SH.XPD.CHEX.GD.ZS`, `SH.XPD.OOPC.CH.ZS`, `SP.DYN.LE00.IN`, `SP.DYN.IMRT.IN`, `NY.GDP.PCAP.CD`) for 2015–2024.
   - Contains no individual-level data; all official reporting lags (`NULL` values) are preserved rather than fabricated.
2. **Synthetic De-Identified Hospital Operations Data (`raw_encounters.csv`, `raw_billing.csv`, `raw_patients.csv`)**
   - Deterministic (`seed = 42`), HIPAA/GDPR-safe synthetic operational encounters modeled on realistic medical tourism cost differentials, clinical risk structures, and hospital utilization patterns.
   - Individual patient clinical records cannot be published openly without legal authorization; using transparently documented synthetic data demonstrates end-to-end clinical analytics architecture without exposing Protected Health Information (PHI).

## 2. Regulatory Alignment Across Jurisdictions

Operating an international healthcare evaluation network across the UAE, Europe, Asia, and North America touches multiple statutory regimes:

| Jurisdiction | Primary Regulation | Key Analytical & Engineering Controls Implemented / Required |
| --- | --- | --- |
| **United Arab Emirates (GCC)** | **UAE Federal Law No. 2 of 2019** (Use of ICT in Health Fields) & **PDPL** | Health data localization rules apply to clinical PHI generated in the UAE; cross-border analytics pipelines must aggregate or anonymize data before export outside national borders and maintain immutable audit trails (`etl_data_quality_audit`). |
| **European Union & Sweden** | **EU GDPR (Art. 9 — Special Category Health Data)** & **Swedish Patient Data Act (PDL)** | Data minimization (store age bands instead of DOB; zero direct identifiers), explicit purpose limitation, documented imputation/processing lineage, and strict separation of pseudonymous tokens from identity lookup tables. |
| **United States** | **HIPAA Privacy & Security Rules (Safe Harbor De-Identification)** | Removal of all 18 Safe Harbor identifiers (names, exact dates of birth, geographic subdivisions smaller than country/city-level provider aggregates, phone/email, MRNs). Synthetic SHA-256 salted tokens (`PT-...`) replace medical record numbers. |
| **Asia-Pacific Hubs** | **Singapore PDPA, Thailand PDPA, India DPDP Act 2023** | Consent-based cross-border transfer agreements with partner hospitals, role-based access control (RBAC) in production warehouses, and encrypted-at-rest storage. |

## 3. Data Quality & Audit Controls in ETL

Every pipeline run automatically enforces and logs 10 validation checks in `etl_data_quality_audit`:
- **Entity Standardization:** Resolves inconsistent partner feed labels (e.g., `"UAE"`, `"U.A.E."`, `"United Arab Emirates"` -> `ARE`; mixed `DD/MM/YYYY` and `YYYY-MM-DD` dates -> ISO-8601).
- **Deduplication & Quarantine:** Isolates duplicate `encounter_id` records and impossible clinical values (e.g., negative length of stay, satisfaction scores `> 5.0`, negative billing) into `data/processed/quarantined_records.csv` instead of silently dropping or corrupting downstream averages.
- **Referential Integrity:** Validates foreign keys prior to warehouse load and runs `PRAGMA foreign_key_check` post-load.
- **Transparent Imputation:** Missing patient satisfaction responses (`3.2%`) are imputed at the hospital median for dashboard rollups while explicitly flagged (`satisfaction_imputed = 1`), and **excluded** from OLS regression modeling so coefficient estimates remain unbiased.
