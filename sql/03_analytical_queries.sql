-- =============================================================================
-- Global Healthcare Operations & Medical Tourism Analytics
-- File: sql/03_analytical_queries.sql
-- Purpose: Business & Clinical Decision Queries for Partner Provider Networks
-- =============================================================================

-- Q1: Top 10 High-Value Partner Hospitals (High Quality + High Cost Savings)
SELECT
    quality_rank,
    hospital_name,
    city,
    country_name,
    CASE WHEN jci_accredited = 1 THEN 'Yes' ELSE 'No' END AS jci,
    total_encounters,
    composite_quality_score,
    readmission_rate_pct,
    avg_satisfaction,
    avg_procedure_cost_usd,
    avg_savings_pct
FROM vw_hospital_scorecard
ORDER BY composite_quality_score DESC
LIMIT 10;

-- Q2: Specialty-Level Risk, Wait Time, and Cross-Border Cost Savings Summary
SELECT
    p.specialty,
    COUNT(e.encounter_id)                          AS encounters,
    SUM(e.is_medical_tourist)                      AS medical_tourists,
    ROUND(AVG(e.wait_time_days), 1)                AS avg_wait_days,
    ROUND(AVG(e.length_of_stay_days), 1)           AS avg_los_days,
    ROUND(AVG(p.benchmark_los_days), 1)            AS benchmark_los_days,
    ROUND(100.0 * AVG(e.readmission_30d_flag), 2)  AS readmission_pct,
    ROUND(100.0 * AVG(e.complication_flag), 2)     AS complication_pct,
    ROUND(AVG(b.procedure_cost_usd), 0)            AS avg_cost_usd,
    ROUND(AVG(CASE WHEN e.is_medical_tourist = 1 THEN b.net_savings_pct END), 1) AS intl_savings_pct
FROM fact_encounters e
JOIN dim_procedure p ON e.procedure_code = p.procedure_code
JOIN fact_billing b  ON e.encounter_id = b.encounter_id
GROUP BY p.specialty
ORDER BY encounters DESC;

-- Q3: Best Destination Hub per Procedure for US-Based Medical Tourists
WITH us_outbound AS (
    SELECT
        p.procedure_name,
        c.country_name                             AS destination,
        COUNT(e.encounter_id)                      AS cases,
        ROUND(AVG(b.total_episode_cost_usd), 0)    AS avg_total_usd,
        ROUND(AVG(b.net_savings_pct), 1)           AS avg_savings_pct,
        ROUND(100.0 * AVG(e.readmission_30d_flag), 2) AS readmission_pct,
        ROUND(AVG(e.patient_satisfaction), 2)      AS avg_satisfaction,
        ROW_NUMBER() OVER (
            PARTITION BY p.procedure_code
            ORDER BY AVG(e.clinical_outcome_score) - (AVG(b.total_episode_cost_usd) / 1000.0) DESC
        ) AS value_rank
    FROM fact_encounters e
    JOIN dim_patient pt   ON e.patient_token = pt.patient_token
    JOIN dim_hospital h   ON e.hospital_id = h.hospital_id
    JOIN dim_country c    ON h.country_code = c.country_code
    JOIN dim_procedure p  ON e.procedure_code = p.procedure_code
    JOIN fact_billing b   ON e.encounter_id = b.encounter_id
    WHERE pt.origin_country_code = 'USA'
      AND e.is_medical_tourist = 1
    GROUP BY p.procedure_code, c.country_code
    HAVING COUNT(e.encounter_id) >= 10
)
SELECT
    procedure_name,
    destination,
    cases,
    avg_total_usd,
    avg_savings_pct,
    readmission_pct,
    avg_satisfaction
FROM us_outbound
WHERE value_rank = 1
ORDER BY avg_savings_pct DESC;

-- Q4: Capacity Stress Analysis — Bed Occupancy vs. Wait Times & Readmissions
SELECT
    CASE
        WHEN h.avg_bed_occupancy_pct >= 88 THEN 'High Utilization (>=88%)'
        WHEN h.avg_bed_occupancy_pct >= 78 THEN 'Optimal Utilization (78-87%)'
        ELSE 'Spare Capacity (<78%)'
    END AS occupancy_band,
    COUNT(DISTINCT h.hospital_id)                 AS hospitals,
    COUNT(e.encounter_id)                         AS encounters,
    ROUND(AVG(e.wait_time_days), 2)               AS avg_wait_days,
    ROUND(100.0 * AVG(e.readmission_30d_flag), 2) AS readmission_rate_pct,
    ROUND(AVG(e.patient_satisfaction), 2)         AS avg_satisfaction
FROM dim_hospital h
JOIN fact_encounters e ON h.hospital_id = e.hospital_id
GROUP BY occupancy_band
ORDER BY avg_wait_days DESC;

-- Q5: Billing Anomaly Audit — Encounters > 2x Procedure Median Cost
WITH proc_avg AS (
    SELECT
        e.procedure_code,
        AVG(b.procedure_cost_usd) AS mean_cost
    FROM fact_encounters e
    JOIN fact_billing b ON e.encounter_id = b.encounter_id
    GROUP BY e.procedure_code
)
SELECT
    e.encounter_id,
    h.hospital_name,
    c.country_name,
    p.procedure_name,
    ROUND(b.procedure_cost_usd, 0)     AS billed_usd,
    ROUND(pa.mean_cost, 0)             AS procedure_avg_usd,
    ROUND(b.procedure_cost_usd / pa.mean_cost, 2) AS cost_ratio,
    e.complication_flag,
    e.length_of_stay_days
FROM fact_encounters e
JOIN fact_billing b  ON e.encounter_id = b.encounter_id
JOIN dim_hospital h  ON e.hospital_id = h.hospital_id
JOIN dim_country c   ON h.country_code = c.country_code
JOIN dim_procedure p ON e.procedure_code = p.procedure_code
JOIN proc_avg pa     ON e.procedure_code = pa.procedure_code
WHERE b.procedure_cost_usd > pa.mean_cost * 2.0
ORDER BY cost_ratio DESC
LIMIT 15;

-- Q6: Referral Channel Economics & Patient Experience
SELECT
    e.referral_channel,
    COUNT(e.encounter_id)                         AS encounters,
    ROUND(100.0 * AVG(e.is_medical_tourist), 1)   AS intl_share_pct,
    ROUND(AVG(e.wait_time_days), 1)               AS avg_wait_days,
    ROUND(AVG(b.net_savings_pct), 1)              AS avg_savings_pct,
    ROUND(AVG(e.patient_satisfaction), 2)         AS avg_satisfaction
FROM fact_encounters e
JOIN fact_billing b ON e.encounter_id = b.encounter_id
GROUP BY e.referral_channel
ORDER BY encounters DESC;

-- Q7: Real World Bank Macro Health Efficiency vs. Hospital Network Benchmarks
SELECT
    country_name,
    wb_health_spend_pc_usd,
    wb_oop_pct_spend,
    wb_beds_per_1000,
    wb_life_expectancy,
    avg_procedure_cost_usd,
    avg_patient_savings_pct,
    avg_readmission_rate_pct
FROM vw_country_macro_vs_ops
ORDER BY wb_health_spend_pc_usd DESC;

-- Q8: ETL Data Quality Audit Summary
SELECT
    dataset_name,
    check_name,
    rows_evaluated,
    rows_flagged,
    action_taken,
    severity
FROM etl_data_quality_audit
ORDER BY audit_id;
