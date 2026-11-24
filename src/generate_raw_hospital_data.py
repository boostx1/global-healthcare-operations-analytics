"""Generate deterministic, HIPAA/GDPR-safe synthetic multi-source hospital operations
and medical tourism datasets modeled on realistic international healthcare economics.

Why synthetic operational data?
Individual patient encounter and billing records are governed by HIPAA, EU GDPR (Art. 9),
and UAE Federal Law No. 2 of 2019. This generator creates de-identified synthetic clinical
operations data paired with real World Bank Open Data macro indicators, and intentionally
injects realistic raw-feed data defects (duplicates, inconsistent country strings, mixed
date formats, negative LOS/costs, orphan IDs, missing feedback) so the ETL pipeline
demonstrates production-grade cleaning and data-quality auditing.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

SEED = 42

COUNTRIES = [
    ("ARE", "United Arab Emirates", "Middle East (GCC)", "High Income", "Mixed Public-Private Insurance", "UAE Federal Law No. 2/2019 (ICT Health)", 1),
    ("SWE", "Sweden", "Northern Europe (Nordic)", "High Income", "Universal Tax-Funded", "EU GDPR + Swedish Patient Data Act (PDL)", 1),
    ("DEU", "Germany", "Western Europe", "High Income", "Statutory Social Health Insurance", "EU GDPR + BDSG", 1),
    ("TUR", "Turkey", "Europe / Middle East", "Upper-Middle Income", "Universal + Private Medical Tourism", "KVKK (Law No. 6698)", 1),
    ("THA", "Thailand", "Southeast Asia", "Upper-Middle Income", "Universal + Private International Hubs", "Thailand PDPA", 1),
    ("IND", "India", "South Asia", "Lower-Middle Income", "Private-Dominant + Public Schemes", "India DPDP Act 2023", 1),
    ("SGP", "Singapore", "Southeast Asia", "High Income", "Mixed Public Savings (Medisave) + Private", "Singapore PDPA", 1),
    ("USA", "United States", "North America", "High Income", "Employer/Private + Medicare/Medicaid", "HIPAA Privacy & Security Rules", 1),
]

# 24 partner hospitals across 8 countries (mix of JCI-accredited & non-JCI, varying tiers & occupancy)
HOSPITALS = [
    # UAE (Dubai & Abu Dhabi — regional medical tourism & GCC anchor hub)
    ("HOSP-ARE-01", "Al Noor Gulf Medical Center", "Dubai", "ARE", "Quaternary", 1, 420, 81.5, 1, "Arabic, English, Russian, Hindi"),
    ("HOSP-ARE-02", "Emirates Horizon Specialist Hospital", "Abu Dhabi", "ARE", "Tertiary", 1, 310, 77.0, 1, "Arabic, English, French"),
    ("HOSP-ARE-03", "Jumeirah Surgical Institute", "Dubai", "ARE", "Specialty Center", 1, 145, 74.2, 1, "Arabic, English, Swedish"),
    ("HOSP-ARE-04", "Sharjah Coastal General Hospital", "Sharjah", "ARE", "Tertiary", 0, 260, 86.4, 0, "Arabic, English"),
    # Sweden
    ("HOSP-SWE-01", "Nordic Heart & Ortho Clinic", "Stockholm", "SWE", "Quaternary", 1, 510, 88.2, 1, "Swedish, English, Arabic"),
    ("HOSP-SWE-02", "Vastra Specialist Hospital", "Gothenburg", "SWE", "Tertiary", 1, 380, 85.6, 1, "Swedish, English"),
    ("HOSP-SWE-03", "Skane Regional Care Center", "Malmo", "SWE", "Tertiary", 0, 290, 90.5, 0, "Swedish, English, Danish"),
    # Germany
    ("HOSP-DEU-01", "Bavaria International Klinikum", "Munich", "DEU", "Quaternary", 1, 560, 82.0, 1, "German, English, Arabic, Russian"),
    ("HOSP-DEU-02", "Spree Valley Medical Center", "Berlin", "DEU", "Tertiary", 1, 410, 84.1, 1, "German, English, Turkish"),
    ("HOSP-DEU-03", "Rhine Orthopedic Institute", "Frankfurt", "DEU", "Specialty Center", 0, 190, 80.3, 1, "German, English"),
    # Turkey
    ("HOSP-TUR-01", "Bosphorus International Hospital", "Istanbul", "TUR", "Quaternary", 1, 480, 79.4, 1, "Turkish, English, Arabic, German"),
    ("HOSP-TUR-02", "Anatolia Care & Oncology Hub", "Ankara", "TUR", "Tertiary", 1, 340, 81.8, 1, "Turkish, English, Arabic"),
    ("HOSP-TUR-03", "Aegean Surgical & Dental Center", "Izmir", "TUR", "Specialty Center", 0, 165, 84.9, 1, "Turkish, English, German"),
    # Thailand
    ("HOSP-THA-01", "Siam International Medical Center", "Bangkok", "THA", "Quaternary", 1, 530, 76.5, 1, "Thai, English, Arabic, Mandarin"),
    ("HOSP-THA-02", "Chao Phraya Heart & Spine Hospital", "Bangkok", "THA", "Tertiary", 1, 320, 78.2, 1, "Thai, English, Japanese"),
    ("HOSP-THA-03", "Andaman Wellness & Surgery Clinic", "Phuket", "THA", "Specialty Center", 0, 140, 73.0, 1, "Thai, English, Russian"),
    # India
    ("HOSP-IND-01", "Indraprastha Apex Health Institute", "New Delhi", "IND", "Quaternary", 1, 680, 83.7, 1, "Hindi, English, Arabic, Bengali"),
    ("HOSP-IND-02", "Deccan Cardiac & Transplant Center", "Bengaluru", "IND", "Quaternary", 1, 520, 80.5, 1, "English, Hindi, Kannada, Arabic"),
    ("HOSP-IND-03", "Western Coast Multi-Specialty Hospital", "Mumbai", "IND", "Tertiary", 0, 390, 89.1, 1, "English, Hindi, Marathi"),
    # Singapore
    ("HOSP-SGP-01", "Pacific Rim Quaternary Medical Hub", "Singapore", "SGP", "Quaternary", 1, 490, 83.2, 1, "English, Mandarin, Malay, Arabic"),
    ("HOSP-SGP-02", "Marina Oncology & Diagnostics Center", "Singapore", "SGP", "Specialty Center", 1, 210, 79.0, 1, "English, Mandarin, Indonesian"),
    # United States (High-cost benchmark + tertiary care)
    ("HOSP-USA-01", "Atlantic Academic Medical Center", "Boston", "USA", "Quaternary", 1, 740, 89.4, 1, "English, Spanish, Arabic"),
    ("HOSP-USA-02", "Pacific Precision Surgical Hospital", "San Diego", "USA", "Tertiary", 1, 430, 86.0, 1, "English, Spanish"),
    ("HOSP-USA-03", "Midwest Community General Hospital", "Chicago", "USA", "Tertiary", 0, 360, 91.2, 0, "English, Spanish"),
]

# Country procedure price multiplier relative to US benchmark
COUNTRY_COST_FACTOR = {
    "USA": 1.00,
    "SGP": 0.56,
    "SWE": 0.52,
    "DEU": 0.49,
    "ARE": 0.46,
    "THA": 0.29,
    "TUR": 0.25,
    "IND": 0.19,
}

# Country baseline wait times (days) for elective care
COUNTRY_WAIT_BASE = {
    "ARE": 7.0,
    "THA": 6.5,
    "IND": 8.0,
    "TUR": 7.5,
    "SGP": 9.0,
    "DEU": 16.0,
    "USA": 18.5,
    "SWE": 26.0,
}

PROCEDURES = [
    ("PROC-CARD-01", "Coronary Artery Bypass Graft (CABG)", "Cardiology", 5, 7.0, 92000, 44000, 38000),
    ("PROC-CARD-02", "Cardiac Valve Replacement", "Cardiology", 5, 6.5, 115000, 52000, 46000),
    ("PROC-ORTH-01", "Total Knee Arthroplasty", "Orthopedics", 3, 3.5, 42000, 21000, 18500),
    ("PROC-ORTH-02", "Total Hip Replacement", "Orthopedics", 3, 4.0, 45000, 22500, 19500),
    ("PROC-ORTH-03", "Lumbar Spinal Fusion", "Orthopedics", 4, 4.5, 68000, 31000, 27000),
    ("PROC-ONCO-01", "Targeted Oncology Resection & Protocol", "Oncology", 5, 6.0, 86000, 41000, 36000),
    ("PROC-BARI-01", "Laparoscopic Sleeve Gastrectomy", "Bariatrics", 2, 2.5, 22000, 12500, 10500),
    ("PROC-OPHT-01", "Bilateral Cataract & Premium IOL Surgery", "Ophthalmology", 1, 1.0, 9500, 5200, 4600),
    ("PROC-OPHT-02", "Wavefront-Guided LASIK Correction", "Ophthalmology", 1, 0.0, 5400, 3400, 2900),
    ("PROC-DENT-01", "Full-Arch Zirconia Dental Implants", "Dental & Maxillofacial", 2, 1.0, 28000, 15500, 12500),
    ("PROC-DIAG-01", "Executive Whole-Body MRI & Cardiac Workup", "Diagnostics", 1, 1.0, 7800, 4200, 3600),
    ("PROC-NEUR-01", "Minimally Invasive Microdiscectomy", "Neurosurgery", 4, 3.0, 52000, 25000, 22000),
]

REFERRAL_CHANNELS = [
    ("Medical Tourism Facilitator", 0.34),
    ("Direct Hospital Portal", 0.24),
    ("International Insurer Network", 0.22),
    ("Physician Cross-Border Referral", 0.12),
    ("Corporate Employer Program", 0.08),
]

# Dirty country aliases injected into raw_hospitals / raw_patients for ETL standardization
DIRTY_COUNTRY_ALIASES = {
    "ARE": ["ARE", "UAE", "U.A.E.", "United Arab Emirates", "are"],
    "TUR": ["TUR", "Turkey", "Turkiye", "tur"],
    "USA": ["USA", "US", "United States", "usa"],
    "SWE": ["SWE", "Sweden", "SE"],
    "DEU": ["DEU", "Germany", "DE"],
    "THA": ["THA", "Thailand", "TH"],
    "IND": ["IND", "India", "IN"],
    "SGP": ["SGP", "Singapore", "SG"],
}


def make_patient_token(idx: int) -> str:
    digest = hashlib.sha256(f"SYNTH-PATIENT-SALT-2026-{idx}".encode("utf-8")).hexdigest()[:12].upper()
    return f"PT-{digest}"


def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Write dim_country seed CSV
    with (RAW_DIR / "raw_countries.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "country_code", "country_name", "region", "income_group",
            "health_system_model", "regulatory_framework", "is_major_destination"
        ])
        w.writerows(COUNTRIES)

    # 2. Write raw_hospitals.csv (with minor dirty country code strings to clean in ETL)
    with (RAW_DIR / "raw_hospitals.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "hospital_id", "hospital_name", "city", "country_raw", "hospital_tier",
            "jci_accredited", "licensed_beds", "avg_bed_occupancy_pct",
            "intl_patient_desk", "languages_supported"
        ])
        for i, h in enumerate(HOSPITALS):
            c_code = h[3]
            dirty_c = DIRTY_COUNTRY_ALIASES[c_code][i % len(DIRTY_COUNTRY_ALIASES[c_code])]
            w.writerow([h[0], h[1], h[2], dirty_c, h[4], h[5], h[6], h[7], h[8], h[9]])

    # 3. Write raw_procedures.csv
    with (RAW_DIR / "raw_procedures.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "procedure_code", "procedure_name", "specialty", "clinical_complexity_score",
            "benchmark_los_days", "us_benchmark_cost_usd", "eu_benchmark_cost_usd", "gcc_benchmark_cost_usd"
        ])
        w.writerows(PROCEDURES)

    # 4. Generate 4,200 synthetic de-identified patients
    n_patients = 4200
    origin_codes = ["USA", "SWE", "DEU", "ARE", "SGP", "TUR", "THA", "IND"]
    origin_probs = [0.27, 0.14, 0.14, 0.15, 0.08, 0.08, 0.07, 0.07]
    age_bands = ["18-34", "35-49", "50-64", "65-74", "75+"]
    age_probs = [0.16, 0.25, 0.31, 0.20, 0.08]
    payer_types = ["Self-Pay", "Private International", "Employer Sponsored", "Public Cross-Border"]
    payer_probs = [0.38, 0.31, 0.18, 0.13]

    patients = []
    for i in range(1, n_patients + 1):
        token = make_patient_token(i)
        orig = str(rng.choice(origin_codes, p=origin_probs))
        age = str(rng.choice(age_bands, p=age_probs))
        sex = str(rng.choice(["F", "M"]))
        # Higher comorbidity for older cohorts
        age_idx = age_bands.index(age)
        comorb = int(np.clip(rng.poisson(0.55 + 0.55 * age_idx), 0, 5))
        payer = str(rng.choice(payer_types, p=payer_probs))
        patients.append((token, orig, age, sex, comorb, payer))

    with (RAW_DIR / "raw_patients.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["patient_token", "origin_country_raw", "age_band", "sex_at_birth", "comorbidity_index", "payer_type"])
        for i, p in enumerate(patients):
            raw_orig = DIRTY_COUNTRY_ALIASES[p[1]][0] if (i % 17 != 0) else DIRTY_COUNTRY_ALIASES[p[1]][1]
            w.writerow([p[0], raw_orig, p[2], p[3], p[4], p[5]])

    # 5. Generate 6,000 hospital & medical tourism encounters across 2023-01-01 to 2025-12-31
    n_encounters = 6000
    start_dt = date(2023, 1, 1)
    total_days = (date(2025, 12, 31) - start_dt).days

    hosp_lookup = {h[0]: h for h in HOSPITALS}
    hosp_by_country: dict[str, list[str]] = {}
    for h in HOSPITALS:
        hosp_by_country.setdefault(h[3], []).append(h[0])

    # Destination preference weights for medical tourists by origin
    dest_prefs = {
        "USA": (["THA", "TUR", "IND", "ARE", "DEU", "SGP"], [0.24, 0.23, 0.22, 0.14, 0.09, 0.08]),
        "SWE": (["DEU", "TUR", "ARE", "THA", "IND", "SGP"], [0.30, 0.28, 0.20, 0.10, 0.07, 0.05]),
        "DEU": (["TUR", "ARE", "THA", "IND", "SWE", "SGP"], [0.34, 0.22, 0.18, 0.12, 0.08, 0.06]),
        "ARE": (["DEU", "IND", "THA", "TUR", "SGP", "USA"], [0.26, 0.24, 0.18, 0.14, 0.10, 0.08]),
        "SGP": (["THA", "IND", "ARE", "DEU", "TUR", "USA"], [0.30, 0.24, 0.18, 0.12, 0.10, 0.06]),
        "TUR": (["DEU", "ARE", "USA", "SWE", "SGP", "THA"], [0.32, 0.26, 0.14, 0.12, 0.09, 0.07]),
        "THA": (["SGP", "ARE", "DEU", "IND", "USA", "TUR"], [0.30, 0.22, 0.18, 0.14, 0.10, 0.06]),
        "IND": (["ARE", "SGP", "DEU", "THA", "USA", "TUR"], [0.30, 0.25, 0.18, 0.12, 0.09, 0.06]),
    }

    proc_weights = np.array([0.07, 0.05, 0.13, 0.11, 0.08, 0.07, 0.11, 0.10, 0.08, 0.09, 0.06, 0.05])
    proc_weights = proc_weights / proc_weights.sum()
    ref_names = [r[0] for r in REFERRAL_CHANNELS]
    ref_probs = [r[1] for r in REFERRAL_CHANNELS]

    enc_rows = []
    bill_rows = []

    # Seasonal probability across days (slight peak in Q1 & Q4 for elective medical tourism + mild YoY growth)
    day_offsets = np.arange(total_days + 1)
    dates_all = [start_dt + timedelta(days=int(d)) for d in day_offsets]
    day_weights = np.array([
        (1.0 + 0.12 * (dt.year - 2023)) * (1.14 if dt.month in (1, 2, 3, 10, 11) else 0.94 if dt.month in (7, 8) else 1.0)
        for dt in dates_all
    ])
    day_weights /= day_weights.sum()

    for idx in range(1, n_encounters + 1):
        enc_id = f"ENC-{idx:06d}"
        bill_id = f"BIL-{idx:06d}"
        pt = patients[int(rng.integers(0, n_patients))]
        pt_token, orig_country, age_band, _, comorb, payer = pt

        # ~64% medical tourism encounters, ~36% domestic hospital encounters
        is_mt = int(rng.random() < 0.64)
        if is_mt:
            dest_choices, dest_p = dest_prefs[orig_country]
            dest_country = str(rng.choice(dest_choices, p=dest_p))
        else:
            dest_country = orig_country

        # Pick hospital within destination country (slight preference for JCI hubs for medical tourists)
        cand_hosps = hosp_by_country[dest_country]
        if is_mt and len(cand_hosps) > 1:
            hw = np.array([2.2 if hosp_lookup[hid][5] == 1 else 0.7 for hid in cand_hosps])
            hw /= hw.sum()
            hosp_id = str(rng.choice(cand_hosps, p=hw))
        else:
            hosp_id = str(rng.choice(cand_hosps))

        hosp = hosp_lookup[hosp_id]
        jci = hosp[5]
        occ_pct = hosp[7]
        intl_desk = hosp[8]

        proc = PROCEDURES[int(rng.choice(len(PROCEDURES), p=proc_weights))]
        proc_code, _, _, complexity, bench_los, us_cost, eu_cost, gcc_cost = proc

        admit_dt = dates_all[int(rng.choice(len(dates_all), p=day_weights))]

        # Referral channel
        if is_mt:
            ref = str(rng.choice(ref_names, p=ref_probs))
        else:
            ref = str(rng.choice(["Direct Hospital Portal", "Physician Cross-Border Referral", "Corporate Employer Program"], p=[0.62, 0.25, 0.13]))

        # Wait time: driven by destination base, occupancy pressure, complexity, and medical tourist fast-track
        occ_pressure = max(0.0, (occ_pct - 78.0) * 0.65)
        mt_fasttrack = -3.2 if (is_mt and intl_desk == 1) else 0.0
        wait_mean = max(2.0, COUNTRY_WAIT_BASE[dest_country] + occ_pressure + 1.1 * complexity + mt_fasttrack)
        wait_days = int(np.clip(round(rng.gamma(shape=3.2, scale=wait_mean / 3.2)), 1, 90))

        # Complication probability: driven by complexity, comorbidity, JCI accreditation, and occupancy stress
        comp_logit = (
            -3.55
            + 0.42 * complexity
            + 0.28 * comorb
            - 0.62 * jci
            + 0.045 * max(0.0, occ_pct - 84.0)
        )
        comp_prob = 1.0 / (1.0 + np.exp(-comp_logit))
        comp_flag = int(rng.random() < comp_prob)

        # 30-day readmission probability: strongly linked to complications, JCI, comorbidity, complexity
        readm_logit = (
            -3.40
            + 1.35 * comp_flag
            + 0.30 * complexity
            + 0.24 * comorb
            - 0.58 * jci
            + 0.03 * max(0.0, occ_pct - 85.0)
        )
        readm_prob = 1.0 / (1.0 + np.exp(-readm_logit))
        readm_flag = int(rng.random() < readm_prob)

        # Length of stay (days)
        los_mean = max(0.0, bench_los + 0.35 * comorb + 2.4 * comp_flag - 0.25 * jci + rng.normal(0.0, 0.65))
        los_days = 0 if (bench_los == 0.0 and comp_flag == 0 and rng.random() < 0.85) else int(max(1, round(los_mean)))
        disch_dt = admit_dt + timedelta(days=los_days)

        # Clinical outcome score (0-100)
        outcome = float(np.clip(
            91.5
            + 3.2 * jci
            - 1.3 * complexity
            - 1.1 * comorb
            - 11.5 * comp_flag
            - 7.5 * readm_flag
            + rng.normal(0.0, 3.6),
            42.0,
            100.0,
        ))

        # Patient satisfaction (1.0 - 5.0)
        sat = float(np.clip(
            4.55
            + 0.28 * jci
            + 0.14 * (intl_desk if is_mt else 0)
            - 0.018 * wait_days
            - 0.68 * comp_flag
            - 0.55 * readm_flag
            - 0.04 * max(0, los_days - bench_los)
            + rng.normal(0.0, 0.34),
            1.2,
            5.0,
        ))
        sat = round(sat, 2)

        # Financial episode costs
        country_mult = COUNTRY_COST_FACTOR[dest_country]
        jci_premium = 1.08 if jci == 1 else 0.94
        comp_cost_mult = 1.32 if comp_flag == 1 else 1.0
        noise_mult = float(np.clip(rng.normal(1.0, 0.09), 0.75, 1.35))
        proc_cost = round(us_cost * country_mult * jci_premium * comp_cost_mult * noise_mult, 2)

        # Travel & logistics package for medical tourists (flights, hotel, visa/concierge, companion)
        if is_mt:
            travel_cost = round(float(np.clip(rng.normal(2450 + 185 * los_days, 480), 850, 9500)), 2)
        else:
            travel_cost = 0.0

        total_cost = round(proc_cost + travel_cost, 2)

        # Home-country benchmark cost
        if orig_country == "USA":
            home_bench = float(us_cost)
        elif orig_country in ("SWE", "DEU"):
            home_bench = float(eu_cost)
        elif orig_country == "ARE":
            home_bench = float(gcc_cost)
        else:
            home_bench = round(us_cost * COUNTRY_COST_FACTOR[orig_country], 2)

        # Out-of-pocket share by payer
        oop_map = {
            "Self-Pay": 95.0,
            "Private International": 22.0,
            "Employer Sponsored": 14.0,
            "Public Cross-Border": 18.0,
        }
        oop_share = round(float(np.clip(rng.normal(oop_map[payer], 6.0), 0.0, 100.0)), 1)
        bill_status = str(rng.choice(["Settled", "Insurance Pending", "Audit Review"], p=[0.84, 0.12, 0.04]))

        # Intentionally mix date format on 5% of raw rows (DD/MM/YYYY vs YYYY-MM-DD) for ETL standardization
        admit_str = admit_dt.strftime("%d/%m/%Y") if (idx % 20 == 0) else admit_dt.isoformat()
        disch_str = disch_dt.isoformat()

        # Intentionally leave ~3.2% satisfaction values missing (non-respondents) for ETL imputation + flagging
        sat_raw = "" if (idx % 31 == 0) else f"{sat:.2f}"

        enc_rows.append([
            enc_id, pt_token, hosp_id, proc_code, is_mt, ref,
            admit_str, disch_str, wait_days, los_days,
            comp_flag, readm_flag, f"{outcome:.2f}", sat_raw
        ])
        bill_rows.append([
            bill_id, enc_id, f"{proc_cost:.2f}", f"{travel_cost:.2f}",
            f"{total_cost:.2f}", f"{home_bench:.2f}", f"{oop_share:.1f}", bill_status
        ])

    # -------------------------------------------------------------------------
    # Intentionally inject realistic raw-feed data defects to test ETL cleaning
    # -------------------------------------------------------------------------
    # Defect A: 18 exact/near-duplicate encounter rows
    for dup_i in range(18):
        enc_rows.append(list(enc_rows[dup_i * 50]))
        bill_rows.append(list(bill_rows[dup_i * 50]))

    # Defect B: 6 corrupted encounters with negative LOS or invalid satisfaction (> 5.0)
    for j in range(6):
        bad_id = f"ENC-BAD-{j+1:03d}"
        bad_bill = f"BIL-BAD-{j+1:03d}"
        enc_rows.append([
            bad_id, patients[j][0], "HOSP-ARE-01", "PROC-ORTH-01", 1, "Direct Hospital Portal",
            "2024-06-15", "2024-06-12", 5, -3, 0, 0, "88.00", "6.40"
        ])
        bill_rows.append([bad_bill, bad_id, "-1250.00", "900.00", "-350.00", "42000.00", "100.0", "Audit Review"])

    # Defect C: 5 orphan encounters pointing to non-existent hospital IDs
    for j in range(5):
        orp_id = f"ENC-ORP-{j+1:03d}"
        orp_bill = f"BIL-ORP-{j+1:03d}"
        enc_rows.append([
            orp_id, patients[j + 10][0], "HOSP-UNKNOWN-99", "PROC-CARD-01", 1, "Medical Tourism Facilitator",
            "2024-08-10", "2024-08-17", 10, 7, 0, 0, "91.00", "4.50"
        ])
        bill_rows.append([orp_bill, orp_id, "32000.00", "2500.00", "34500.00", "92000.00", "20.0", "Settled"])

    with (RAW_DIR / "raw_encounters.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "encounter_id", "patient_token", "hospital_id", "procedure_code",
            "is_medical_tourist", "referral_channel", "admission_date", "discharge_date",
            "wait_time_days", "length_of_stay_days", "complication_flag",
            "readmission_30d_flag", "clinical_outcome_score", "patient_satisfaction"
        ])
        w.writerows(enc_rows)

    with (RAW_DIR / "raw_billing.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "billing_id", "encounter_id", "procedure_cost_usd", "travel_logistics_usd",
            "total_episode_cost_usd", "home_benchmark_cost_usd", "out_of_pocket_share_pct", "billing_status"
        ])
        w.writerows(bill_rows)

    print(
        f"Generated raw multi-source operational feeds in {RAW_DIR}: "
        f"{len(HOSPITALS)} hospitals, {len(PROCEDURES)} procedures, "
        f"{len(patients)} de-identified patients, {len(enc_rows)} raw encounters (incl. injected DQ defects)."
    )


if __name__ == "__main__":
    main()
