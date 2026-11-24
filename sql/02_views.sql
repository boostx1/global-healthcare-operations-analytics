-- =============================================================================
-- Global Healthcare Operations & Medical Tourism Analytics
-- File: sql/02_views.sql
-- Purpose: Production Analytical Views for Dashboards, Excel, and Partner BI
-- =============================================================================

DROP VIEW IF EXISTS vw_hospital_scorecard;
DROP VIEW IF EXISTS vw_medical_tourism_corridors;
DROP VIEW IF EXISTS vw_jci_accreditation_impact;
DROP VIEW IF EXISTS vw_monthly_operations_kpi;
DROP VIEW IF EXISTS vw_country_macro_vs_ops;

-- -----------------------------------------------------------------------------
-- View 1: Partner Hospital Performance Scorecard (Composite Quality-Value Index)
-- -----------------------------------------------------------------------------
CREATE VIEW vw_hospital_scorecard AS
WITH hospital_base AS (
    SELECT
        h.hospital_id,
        h.hospital_name,
        h.city,
        c.country_code,
        c.country_name,
        c.region,
        h.hospital_tier,
        h.jci_accredited,
        h.licensed_beds,
        h.avg_bed_occupancy_pct,
        COUNT(e.encounter_id)                                          AS total_encounters,
        SUM(e.is_medical_tourist)                                      AS intl_encounters,
        ROUND(100.0 * AVG(e.is_medical_tourist), 1)                    AS intl_patient_share_pct,
        ROUND(AVG(e.wait_time_days), 2)                                AS avg_wait_days,
        ROUND(AVG(e.length_of_stay_days), 2)                           AS avg_los_days,
        ROUND(100.0 * AVG(e.readmission_30d_flag), 2)                  AS readmission_rate_pct,
        ROUND(100.0 * AVG(e.complication_flag), 2)                     AS complication_rate_pct,
        ROUND(AVG(e.clinical_outcome_score), 2)                        AS avg_clinical_outcome,
        ROUND(AVG(e.patient_satisfaction), 2)                          AS avg_satisfaction,
        ROUND(AVG(b.procedure_cost_usd), 0)                            AS avg_procedure_cost_usd,
        ROUND(AVG(b.total_episode_cost_usd), 0)                        AS avg_total_cost_usd,
        ROUND(AVG(b.net_savings_pct), 1)                               AS avg_savings_pct,
        ROUND(AVG(p.clinical_complexity_score), 2)                     AS avg_case_complexity
    FROM dim_hospital h
    JOIN dim_country c     ON h.country_code = c.country_code
    JOIN fact_encounters e ON h.hospital_id = e.hospital_id
    JOIN fact_billing b    ON e.encounter_id = b.encounter_id
    JOIN dim_procedure p   ON e.procedure_code = p.procedure_code
    GROUP BY h.hospital_id
),
scored AS (
    SELECT
        *,
        -- Composite Value-Based Quality Score (0-100):
        -- 35% clinical outcome + 25% low readmission + 20% low complication + 20% patient satisfaction
        ROUND(
            0.35 * avg_clinical_outcome
            + 0.25 * MAX(0.0, 100.0 - (readmission_rate_pct * 5.0))
            + 0.20 * MAX(0.0, 100.0 - (complication_rate_pct * 5.0))
            + 0.20 * (avg_satisfaction * 20.0),
            2
        ) AS composite_quality_score
    FROM hospital_base
)
SELECT
    *,
    DENSE_RANK() OVER (ORDER BY composite_quality_score DESC) AS quality_rank,
    DENSE_RANK() OVER (PARTITION BY country_code ORDER BY composite_quality_score DESC) AS country_rank
FROM scored;

-- -----------------------------------------------------------------------------
-- View 2: Cross-Border Medical Tourism Corridors (Origin -> Destination)
-- -----------------------------------------------------------------------------
CREATE VIEW vw_medical_tourism_corridors AS
SELECT
    orig.country_code                         AS origin_country_code,
    orig.country_name                         AS origin_country,
    dest.country_code                         AS destination_country_code,
    dest.country_name                         AS destination_country,
    COUNT(e.encounter_id)                     AS encounter_volume,
    ROUND(AVG(b.home_benchmark_cost_usd), 0)  AS avg_home_cost_usd,
    ROUND(AVG(b.total_episode_cost_usd), 0)   AS avg_destination_total_usd,
    ROUND(AVG(b.net_savings_usd), 0)          AS avg_net_savings_usd,
    ROUND(AVG(b.net_savings_pct), 1)          AS avg_net_savings_pct,
    ROUND(AVG(e.wait_time_days), 1)           AS avg_wait_days,
    ROUND(100.0 * AVG(e.readmission_30d_flag), 2) AS readmission_rate_pct,
    ROUND(AVG(e.patient_satisfaction), 2)     AS avg_satisfaction
FROM fact_encounters e
JOIN dim_patient pt    ON e.patient_token = pt.patient_token
JOIN dim_country orig  ON pt.origin_country_code = orig.country_code
JOIN dim_hospital h    ON e.hospital_id = h.hospital_id
JOIN dim_country dest  ON h.country_code = dest.country_code
JOIN fact_billing b    ON e.encounter_id = b.encounter_id
WHERE e.is_medical_tourist = 1
GROUP BY orig.country_code, dest.country_code
HAVING COUNT(e.encounter_id) >= 15
ORDER BY encounter_volume DESC;

-- -----------------------------------------------------------------------------
-- View 3: JCI Accreditation Clinical & Operational Impact
-- -----------------------------------------------------------------------------
CREATE VIEW vw_jci_accreditation_impact AS
SELECT
    CASE WHEN h.jci_accredited = 1 THEN 'JCI Accredited' ELSE 'Non-JCI Accredited' END AS accreditation_status,
    h.jci_accredited,
    COUNT(DISTINCT h.hospital_id)                 AS hospital_count,
    COUNT(e.encounter_id)                         AS encounter_count,
    ROUND(100.0 * AVG(e.readmission_30d_flag), 2) AS readmission_rate_pct,
    ROUND(100.0 * AVG(e.complication_flag), 2)    AS complication_rate_pct,
    ROUND(AVG(e.clinical_outcome_score), 2)       AS avg_clinical_outcome,
    ROUND(AVG(e.patient_satisfaction), 2)         AS avg_satisfaction,
    ROUND(AVG(e.wait_time_days), 2)               AS avg_wait_days,
    ROUND(AVG(e.length_of_stay_days), 2)          AS avg_los_days,
    ROUND(AVG(b.procedure_cost_usd), 0)           AS avg_procedure_cost_usd
FROM fact_encounters e
JOIN dim_hospital h ON e.hospital_id = h.hospital_id
JOIN fact_billing b ON e.encounter_id = b.encounter_id
GROUP BY h.jci_accredited;

-- -----------------------------------------------------------------------------
-- View 4: Monthly Operational KPIs with MoM Growth & 3-Month Rolling Averages
-- -----------------------------------------------------------------------------
CREATE VIEW vw_monthly_operations_kpi AS
WITH monthly AS (
    SELECT
        e.admission_month,
        COUNT(e.encounter_id)                         AS total_encounters,
        SUM(e.is_medical_tourist)                     AS medical_tourist_encounters,
        ROUND(AVG(e.wait_time_days), 2)               AS avg_wait_days,
        ROUND(AVG(e.length_of_stay_days), 2)          AS avg_los_days,
        ROUND(100.0 * AVG(e.readmission_30d_flag), 2) AS readmission_rate_pct,
        ROUND(100.0 * AVG(e.complication_flag), 2)    AS complication_rate_pct,
        ROUND(AVG(e.patient_satisfaction), 2)         AS avg_satisfaction,
        ROUND(SUM(b.total_episode_cost_usd), 0)       AS gross_episode_revenue_usd
    FROM fact_encounters e
    JOIN fact_billing b ON e.encounter_id = b.encounter_id
    GROUP BY e.admission_month
)
SELECT
    admission_month,
    total_encounters,
    medical_tourist_encounters,
    ROUND(100.0 * medical_tourist_encounters / total_encounters, 1) AS intl_share_pct,
    LAG(total_encounters, 1) OVER (ORDER BY admission_month) AS prev_month_encounters,
    ROUND(
        100.0 * (total_encounters - LAG(total_encounters, 1) OVER (ORDER BY admission_month))
        / NULLIF(LAG(total_encounters, 1) OVER (ORDER BY admission_month), 0),
        1
    ) AS mom_volume_growth_pct,
    avg_wait_days,
    avg_los_days,
    readmission_rate_pct,
    ROUND(
        AVG(readmission_rate_pct) OVER (ORDER BY admission_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
        2
    ) AS rolling_3m_readmission_pct,
    complication_rate_pct,
    avg_satisfaction,
    gross_episode_revenue_usd
FROM monthly
ORDER BY admission_month;

-- -----------------------------------------------------------------------------
-- View 5: World Bank Real Macro Indicators Joined to Hospital Operations
-- -----------------------------------------------------------------------------
CREATE VIEW vw_country_macro_vs_ops AS
WITH latest_wb AS (
    SELECT
        country_code,
        indicator_name,
        value,
        year,
        ROW_NUMBER() OVER (PARTITION BY country_code, indicator_name ORDER BY year DESC) AS rn
    FROM fact_country_health_indicators
    WHERE value IS NOT NULL
),
wb_pivoted AS (
    SELECT
        country_code,
        MAX(CASE WHEN indicator_name = 'hospital_beds_per_1000' THEN value END)           AS wb_beds_per_1000,
        MAX(CASE WHEN indicator_name = 'physicians_per_1000' THEN value END)              AS wb_physicians_per_1000,
        MAX(CASE WHEN indicator_name = 'health_spend_per_capita_usd' THEN value END)      AS wb_health_spend_pc_usd,
        MAX(CASE WHEN indicator_name = 'health_spend_pct_gdp' THEN value END)             AS wb_health_spend_pct_gdp,
        MAX(CASE WHEN indicator_name = 'out_of_pocket_pct_health_spend' THEN value END)   AS wb_oop_pct_spend,
        MAX(CASE WHEN indicator_name = 'life_expectancy_years' THEN value END)            AS wb_life_expectancy,
        MAX(CASE WHEN indicator_name = 'infant_mortality_per_1000' THEN value END)        AS wb_infant_mortality,
        MAX(CASE WHEN indicator_name = 'gdp_per_capita_usd' THEN value END)               AS wb_gdp_per_capita_usd
    FROM latest_wb
    WHERE rn = 1
    GROUP BY country_code
),
ops_country AS (
    SELECT
        h.country_code,
        COUNT(DISTINCT h.hospital_id)                  AS partner_hospitals,
        SUM(h.jci_accredited)                          AS jci_hospitals,
        COUNT(e.encounter_id)                          AS total_encounters,
        ROUND(AVG(b.procedure_cost_usd), 0)            AS avg_procedure_cost_usd,
        ROUND(AVG(b.net_savings_pct), 1)               AS avg_patient_savings_pct,
        ROUND(100.0 * AVG(e.readmission_30d_flag), 2)  AS avg_readmission_rate_pct,
        ROUND(AVG(e.patient_satisfaction), 2)          AS avg_satisfaction
    FROM dim_hospital h
    JOIN fact_encounters e ON h.hospital_id = e.hospital_id
    JOIN fact_billing b    ON e.encounter_id = b.encounter_id
    GROUP BY h.country_code
)
SELECT
    c.country_code,
    c.country_name,
    c.region,
    c.health_system_model,
    ROUND(w.wb_beds_per_1000, 2)        AS wb_beds_per_1000,
    ROUND(w.wb_physicians_per_1000, 2)  AS wb_physicians_per_1000,
    ROUND(w.wb_health_spend_pc_usd, 0)  AS wb_health_spend_pc_usd,
    ROUND(w.wb_health_spend_pct_gdp, 2) AS wb_health_spend_pct_gdp,
    ROUND(w.wb_oop_pct_spend, 1)        AS wb_oop_pct_spend,
    ROUND(w.wb_life_expectancy, 2)      AS wb_life_expectancy,
    ROUND(w.wb_infant_mortality, 2)     AS wb_infant_mortality,
    ROUND(w.wb_gdp_per_capita_usd, 0)   AS wb_gdp_per_capita_usd,
    o.partner_hospitals,
    o.total_encounters,
    o.avg_procedure_cost_usd,
    o.avg_patient_savings_pct,
    o.avg_readmission_rate_pct,
    o.avg_satisfaction
FROM dim_country c
LEFT JOIN wb_pivoted w ON c.country_code = w.country_code
LEFT JOIN ops_country o ON c.country_code = o.country_code
ORDER BY o.total_encounters DESC;
