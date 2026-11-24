"""Generate 6 publication-quality healthcare analytics visualizations saved to reports/figures/."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "healthcare_ops.db"
FIG_DIR = BASE_DIR / "reports" / "figures"
STATS_JSON = BASE_DIR / "reports" / "statistical_results.json"

NAVY = "#0F3D5E"
TEAL = "#0D9488"
AMBER = "#D97706"
CORAL = "#DC2626"
SLATE = "#475569"
LIGHT_GRID = "#E2E8F0"
BG = "#FFFFFF"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.facecolor": BG,
        "figure.facecolor": BG,
        "axes.edgecolor": "#CBD5E1",
        "axes.linewidth": 0.8,
        "axes.titlesize": 12.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "grid.color": LIGHT_GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.7,
    }
)


def style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="y", alpha=0.8)
    ax.set_axisbelow(True)


def fig_01_corridors_and_savings(conn: sqlite3.Connection) -> None:
    df_dest = pd.read_sql_query(
        """
        SELECT
            c.country_name AS destination,
            c.country_code,
            COUNT(e.encounter_id) AS intl_cases,
            ROUND(AVG(b.procedure_cost_usd), 0) AS avg_proc_cost,
            ROUND(AVG(b.travel_logistics_usd), 0) AS avg_travel_cost,
            ROUND(AVG(b.net_savings_pct), 1) AS avg_savings_pct
        FROM fact_encounters e
        JOIN dim_hospital h ON e.hospital_id = h.hospital_id
        JOIN dim_country c  ON h.country_code = c.country_code
        JOIN dim_patient pt ON e.patient_token = pt.patient_token
        JOIN fact_billing b ON e.encounter_id = b.encounter_id
        WHERE e.is_medical_tourist = 1
          AND pt.origin_country_code IN ('USA', 'SWE', 'DEU', 'ARE')
        GROUP BY c.country_code
        ORDER BY avg_savings_pct DESC
        """,
        conn,
    )
    df_dest = df_dest[df_dest["country_code"] != "USA"].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.8), gridspec_kw={"width_ratios": [1.15, 1.0]})
    fig.suptitle(
        "Cross-Border Medical Tourism Economics: Episode Cost Breakdown & Net Patient Savings",
        fontsize=14, fontweight="bold", color=NAVY, y=0.97,
    )

    y = np.arange(len(df_dest))
    ax1.barh(y, df_dest["avg_proc_cost"] / 1000, color=NAVY, height=0.56, label="Procedure Cost")
    ax1.barh(
        y, df_dest["avg_travel_cost"] / 1000,
        left=df_dest["avg_proc_cost"] / 1000,
        color=AMBER, height=0.56, label="Travel & Logistics"
    )
    ax1.set_yticks(y)
    ax1.set_yticklabels(df_dest["destination"], fontweight="bold")
    ax1.invert_yaxis()
    ax1.set_xlabel("Average Total Episode Cost (USD Thousands)")
    ax1.set_title("Total Episode Cost (Procedure + Travel)", color=NAVY, pad=12)
    ax1.xaxis.set_major_formatter(mtick.FormatStrFormatter("$%.0fk"))
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(True, axis="x", alpha=0.8)
    ax1.set_axisbelow(True)
    ax1.legend(frameon=True, facecolor="white", edgecolor=LIGHT_GRID, loc="upper right", fontsize=9.2)
    for i, r in df_dest.reset_index(drop=True).iterrows():
        tot = (r["avg_proc_cost"] + r["avg_travel_cost"]) / 1000
        ax1.text(tot + 0.65, i, f"${tot:.1f}k", va="center", fontsize=9.2, color=NAVY, fontweight="bold")
    ax1.set_xlim(0, (df_dest["avg_proc_cost"] + df_dest["avg_travel_cost"]).max() / 1000 * 1.24)

    colors = [TEAL if v >= 35 else "#2563EB" if v >= 10 else CORAL for v in df_dest["avg_savings_pct"]]
    ax2.barh(y, df_dest["avg_savings_pct"], color=colors, height=0.56)
    ax2.axvline(0, color=SLATE, linewidth=1.0)
    ax2.set_yticks(y)
    ax2.set_yticklabels([""] * len(df_dest))
    ax2.invert_yaxis()
    ax2.set_xlabel("Average Net Savings vs. Home Benchmark (%)")
    ax2.set_title("Net Patient Savings (High-Cost Origin Cohort)", color=NAVY, pad=12)
    ax2.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(True, axis="x", alpha=0.8)
    ax2.set_axisbelow(True)
    for i, r in df_dest.reset_index(drop=True).iterrows():
        v = r["avg_savings_pct"]
        offset = 2.0 if v >= 0 else -2.0
        ha = "left" if v >= 0 else "right"
        ax2.text(v + offset, i, f"{v:+.1f}% (n={int(r['intl_cases'])})", va="center", ha=ha, fontsize=9, fontweight="bold", color=NAVY)
    ax2.set_xlim(min(-18, df_dest["avg_savings_pct"].min() - 25), df_dest["avg_savings_pct"].max() + 28)

    fig.text(
        0.015, 0.012,
        "Cohort: Outbound medical tourists originating from USA, Sweden, Germany, and UAE (synthetic HIPAA-safe operations dataset; 6,000 total clean encounters).",
        fontsize=8.4, color=SLATE,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.92])
    plt.savefig(FIG_DIR / "01_medical_tourism_corridors_savings.png", dpi=200)
    plt.close(fig)


def fig_02_hospital_quadrant(conn: sqlite3.Connection) -> None:
    df = pd.read_sql_query("SELECT * FROM vw_hospital_scorecard", conn)

    fig, ax = plt.subplots(figsize=(12.0, 7.0))
    med_cost = df["avg_procedure_cost_usd"].median() / 1000
    med_qual = df["composite_quality_score"].median()

    ax.axvline(med_cost, color=SLATE, linestyle="--", linewidth=1.1, alpha=0.75)
    ax.axhline(med_qual, color=SLATE, linestyle="--", linewidth=1.1, alpha=0.75)

    x_min = df["avg_procedure_cost_usd"].min() / 1000 * 0.65
    y_max = df["composite_quality_score"].max() + 4.5
    ax.fill_between([x_min, med_cost], med_qual, y_max, color=TEAL, alpha=0.07)
    ax.text(
        x_min + 0.5, y_max - 0.6,
        "HIGH-VALUE LEADERS\n(Above-Median Quality, Below-Median Cost)",
        fontsize=9.2, fontweight="bold", color=TEAL, va="top",
    )

    for jci_val, label, color, marker in [(1, "JCI Accredited (n=17)", TEAL, "o"), (0, "Non-JCI Accredited (n=7)", CORAL, "D")]:
        sub = df[df["jci_accredited"] == jci_val]
        ax.scatter(
            sub["avg_procedure_cost_usd"] / 1000,
            sub["composite_quality_score"],
            s=sub["total_encounters"] * 1.15,
            c=color, alpha=0.84, edgecolors="white", linewidth=1.2,
            marker=marker, label=label, zorder=3,
        )

    highlight_ids = [
        "HOSP-THA-01", "HOSP-THA-02", "HOSP-SGP-02", "HOSP-IND-01",
        "HOSP-ARE-03", "HOSP-ARE-01", "HOSP-USA-02", "HOSP-USA-03",
        "HOSP-SWE-03", "HOSP-IND-03",
    ]
    highlight = df[df["hospital_id"].isin(highlight_ids)].copy()

    offsets = {
        "HOSP-THA-01": (12, -2),
        "HOSP-THA-02": (12, -4),
        "HOSP-SGP-02": (12, 4),
        "HOSP-IND-01": (12, -4),
        "HOSP-ARE-03": (12, 4),
        "HOSP-ARE-01": (12, -16),
        "HOSP-USA-02": (-128, -18),
        "HOSP-USA-03": (-138, -8),
        "HOSP-SWE-03": (12, -4),
        "HOSP-IND-03": (12, 4),
    }
    for _, r in highlight.iterrows():
        dx, dy = offsets.get(r["hospital_id"], (10, 4))
        short_name = f"{r['hospital_name'].split()[0]} {r['hospital_name'].split()[1]} ({r['country_code']})"
        ax.annotate(
            short_name,
            xy=(r["avg_procedure_cost_usd"] / 1000, r["composite_quality_score"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8.4, color=NAVY, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color="#94A3B8", lw=0.7),
        )

    ax.set_xlabel("Average Procedure Cost (USD Thousands)")
    ax.set_ylabel("Composite Quality Score (0–100)")
    ax.set_title("Partner Hospital Value-Based Care Quadrant: Quality Score vs. Procedure Cost", color=NAVY, pad=14)
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("$%.0fk"))
    ax.set_xlim(x_min, df["avg_procedure_cost_usd"].max() / 1000 * 1.10)
    ax.set_ylim(df["composite_quality_score"].min() - 2.4, y_max)
    style_axes(ax)
    ax.grid(True, axis="both", alpha=0.6)
    ax.legend(frameon=True, facecolor="white", edgecolor=LIGHT_GRID, loc="lower right", fontsize=9.5)

    fig.text(
        0.015, 0.008,
        "Bubble size proportional to encounter volume. Dashed lines mark network medians.\n"
        "Composite Quality Score weights clinical outcome (35%), low readmission (25%), low complications (20%), and patient satisfaction (20%).",
        fontsize=8.2, color=SLATE,
    )
    plt.tight_layout(rect=[0, 0.055, 1, 1])
    plt.savefig(FIG_DIR / "02_hospital_quality_vs_cost_quadrant.png", dpi=200)
    plt.close(fig)


def fig_03_jci_outcomes_ci(stats_data: dict) -> None:
    readm = stats_data["jci_readmission_test"]
    comp = stats_data["jci_complication_test"]

    metrics = ["30-Day Readmission Rate", "Clinical Complication Rate"]
    jci_vals = [readm["group1_rate_pct"], comp["group1_rate_pct"]]
    non_vals = [readm["group2_rate_pct"], comp["group2_rate_pct"]]
    jci_err = [
        [jci_vals[0] - readm["group1_ci95_pct"][0], jci_vals[1] - comp["group1_ci95_pct"][0]],
        [readm["group1_ci95_pct"][1] - jci_vals[0], comp["group1_ci95_pct"][1] - jci_vals[1]],
    ]
    non_err = [
        [non_vals[0] - readm["group2_ci95_pct"][0], non_vals[1] - comp["group2_ci95_pct"][0]],
        [readm["group2_ci95_pct"][1] - non_vals[0], comp["group2_ci95_pct"][1] - non_vals[1]],
    ]

    fig, ax = plt.subplots(figsize=(9.8, 5.9))
    x = np.arange(len(metrics))
    width = 0.34

    b1 = ax.bar(x - width / 2, jci_vals, width, yerr=jci_err, capsize=6, color=TEAL, label=f"JCI Accredited (n={readm['group1_n']:,})", error_kw={"ecolor": NAVY, "lw": 1.4})
    b2 = ax.bar(x + width / 2, non_vals, width, yerr=non_err, capsize=6, color=CORAL, label=f"Non-JCI Accredited (n={readm['group2_n']:,})", error_kw={"ecolor": NAVY, "lw": 1.4})

    for bars, errs in [(b1, jci_err[1]), (b2, non_err[1])]:
        for bar, e in zip(bars, errs):
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + e + 0.45, f"{h:.2f}%", ha="center", va="bottom", fontweight="bold", fontsize=10, color=NAVY)

    for i, (test_res, top_ci) in enumerate([(readm, readm["group2_ci95_pct"][1]), (comp, comp["group2_ci95_pct"][1])]):
        y_br = top_ci + 2.4
        x1, x2 = x[i] - width / 2, x[i] + width / 2
        ax.plot([x1, x1, x2, x2], [y_br - 0.45, y_br, y_br, y_br - 0.45], color=NAVY, lw=1.2)
        p_txt = "p < 0.001" if test_res["p_value"] < 0.001 else f"p = {test_res['p_value']:.4f}"
        ax.text(
            x[i], y_br + 0.35,
            f"RRR: {test_res['relative_risk_reduction_pct']:.1f}% | OR = {test_res['odds_ratio']:.2f} ({p_txt})",
            ha="center", va="bottom", fontsize=9.3, fontweight="bold", color=NAVY,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontweight="bold", fontsize=11)
    ax.set_ylabel("Adverse Event Rate (%) with 95% Wilson CI")
    ax.set_title("Impact of JCI Hospital Accreditation on Clinical Safety Outcomes", color=NAVY, pad=14)
    ax.set_ylim(0, 23.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    style_axes(ax)
    ax.legend(frameon=True, facecolor="white", edgecolor=LIGHT_GRID, loc="upper left", fontsize=9.8)

    fig.text(
        0.015, 0.012,
        "Error bars indicate 95% Wilson score confidence intervals. Statistical significance evaluated via two-proportion Z-test and Pearson Chi-square test.",
        fontsize=8.3, color=SLATE,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(FIG_DIR / "03_jci_clinical_outcomes_ci.png", dpi=200)
    plt.close(fig)


def fig_04_monthly_trends(conn: sqlite3.Connection) -> None:
    df = pd.read_sql_query("SELECT * FROM vw_monthly_operations_kpi", conn)
    x = np.arange(len(df))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.2, 7.2), sharex=True, gridspec_kw={"height_ratios": [1.1, 1.0]})
    fig.suptitle("Monthly Hospital Operations & Medical Tourism Performance Trends (2023–2025)", fontsize=14, fontweight="bold", color=NAVY, y=0.98)

    ax1.bar(x, df["total_encounters"], color="#CBD5E1", width=0.72, label="Total Encounters")
    ax1.bar(x, df["medical_tourist_encounters"], color=NAVY, width=0.72, label="International Medical Tourists")
    ax1.set_ylabel("Monthly Encounters")
    ax1.set_title("Encounter Volume Growth & International Patient Mix", color=NAVY, pad=8)
    style_axes(ax1)
    ax1.legend(frameon=False, loc="upper left")

    ax2.plot(x, df["readmission_rate_pct"], color="#94A3B8", marker="o", markersize=4, linewidth=1.2, alpha=0.8, label="Monthly 30-Day Readmission (%)")
    ax2.plot(x, df["rolling_3m_readmission_pct"], color=CORAL, linewidth=2.5, label="3-Month Rolling Readmission (%)")
    ax2.set_ylabel("30-Day Readmission Rate (%)", color=CORAL, fontweight="bold")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax2.set_ylim(0, max(df["readmission_rate_pct"].max() * 1.35, 16))
    style_axes(ax2)

    ax2b = ax2.twinx()
    ax2b.plot(x, df["avg_wait_days"], color=TEAL, linestyle="--", linewidth=2.0, marker="s", markersize=3.5, label="Avg Wait Time (Days)")
    ax2b.set_ylabel("Average Wait Time (Days)", color=TEAL, fontweight="bold")
    ax2b.spines["top"].set_visible(False)
    ax2b.set_ylim(0, df["avg_wait_days"].max() * 1.35)

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, frameon=False, loc="upper right", ncol=3, fontsize=9)
    ax2.set_title("Clinical Stability (3-Month Rolling Readmission) & Access Wait Times", color=NAVY, pad=8)

    tick_idx = np.arange(0, len(df), 3)
    ax2.set_xticks(tick_idx)
    ax2.set_xticklabels(df["admission_month"].iloc[tick_idx], rotation=30, ha="right")
    ax2.set_xlabel("Admission Month (YYYY-MM)")

    plt.tight_layout(rect=[0, 0.01, 1, 0.94])
    plt.savefig(FIG_DIR / "04_monthly_volume_readmission_trends.png", dpi=200)
    plt.close(fig)


def fig_05_worldbank_macro(conn: sqlite3.Connection) -> None:
    df = pd.read_sql_query("SELECT * FROM vw_country_macro_vs_ops", conn)
    df = df.dropna(subset=["wb_health_spend_pc_usd", "wb_life_expectancy", "wb_oop_pct_spend"]).copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.0, 6.0))
    fig.suptitle(
        "Real-World Macro Health System Benchmarks (Official World Bank Open Data API)",
        fontsize=14, fontweight="bold", color=NAVY, y=0.97,
    )

    sizes = df["wb_beds_per_1000"].fillna(2.5) * 105
    sc = ax1.scatter(
        df["wb_health_spend_pc_usd"] / 1000,
        df["wb_life_expectancy"],
        s=sizes, c=df["wb_oop_pct_spend"], cmap="RdYlGn_r",
        vmin=10, vmax=50, alpha=0.9, edgecolors=NAVY, linewidth=1.2, zorder=3,
    )
    cbar = plt.colorbar(sc, ax=ax1, pad=0.02)
    cbar.set_label("Out-of-Pocket Share (%)", fontsize=9)

    label_offsets = {
        "USA": (-82, -26),
        "SWE": (16, 12),
        "DEU": (20, -10),
        "SGP": (18, -24),
        "ARE": (-32, 22),
        "TUR": (24, 16),
        "THA": (26, -20),
        "IND": (22, 4),
    }
    short_label = {
        "United Arab Emirates": "UAE",
        "United States": "USA",
    }
    for _, r in df.iterrows():
        dx, dy = label_offsets.get(r["country_code"], (12, 8))
        cname = short_label.get(r["country_name"], r["country_name"])
        ax1.annotate(
            f"{cname} (${r['wb_health_spend_pc_usd']:,.0f})",
            xy=(r["wb_health_spend_pc_usd"] / 1000, r["wb_life_expectancy"]),
            xytext=(dx, dy), textcoords="offset points",
            fontsize=8.6, fontweight="bold", color=NAVY,
            arrowprops=dict(arrowstyle="-", color="#64748B", lw=0.75),
        )

    ax1.set_xlabel("Current Health Expenditure per Capita (USD Thousands)")
    ax1.set_ylabel("Life Expectancy at Birth (Years)")
    ax1.set_title("Health Spend Efficiency vs. Longevity\n(Bubble Size = Hospital Beds / 1,000)", color=NAVY, pad=10)
    ax1.xaxis.set_major_formatter(mtick.FormatStrFormatter("$%.0fk"))
    style_axes(ax1)
    ax1.grid(True, axis="both", alpha=0.6)
    ax1.set_xlim(-0.8, df["wb_health_spend_pc_usd"].max() / 1000 * 1.14)
    ax1.set_ylim(df["wb_life_expectancy"].min() - 2.2, df["wb_life_expectancy"].max() + 2.8)

    df_oop = df.sort_values("wb_oop_pct_spend", ascending=True)
    bar_colors = [TEAL if v < 20 else AMBER if v < 35 else CORAL for v in df_oop["wb_oop_pct_spend"]]
    y = np.arange(len(df_oop))
    ax2.barh(y, df_oop["wb_oop_pct_spend"], color=bar_colors, height=0.58)
    ax2.set_yticks(y)
    ax2.set_yticklabels(df_oop["country_name"], fontweight="bold")
    ax2.set_xlabel("Out-of-Pocket Health Expenditure (% of Total Health Spend)")
    ax2.set_title("Household Financial Protection Across 8 Nations\n(Lower = Stronger Public/Insurance Coverage)", color=NAVY, pad=10)
    ax2.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(True, axis="x", alpha=0.8)
    ax2.set_axisbelow(True)
    for i, r in df_oop.reset_index(drop=True).iterrows():
        ax2.text(r["wb_oop_pct_spend"] + 1.0, i, f"{r['wb_oop_pct_spend']:.1f}%", va="center", fontsize=9.2, fontweight="bold", color=NAVY)
    ax2.set_xlim(0, df_oop["wb_oop_pct_spend"].max() * 1.22)

    fig.text(
        0.015, 0.012,
        "Source: Live World Bank Open Data API v2 (SH.XPD.CHEX.PC.CD, SP.DYN.LE00.IN, SH.XPD.OOPC.CH.ZS, SH.MED.BEDS.ZS); latest available non-null year per country (2015–2024).",
        fontsize=8.2, color=SLATE,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.92])
    plt.savefig(FIG_DIR / "05_worldbank_macro_benchmarks.png", dpi=200)
    plt.close(fig)


def fig_06_regression_drivers(stats_data: dict) -> None:
    sat_model = stats_data["ols_patient_satisfaction"]
    coefs = [c for c in sat_model["coefficients"] if c["feature"] != "intercept"]
    coefs.sort(key=lambda c: abs(c["std_beta"]), reverse=False)

    pretty_names = {
        "wait_time_days": "Elective Wait Time (Days)",
        "complication_flag": "Clinical Complication (Yes)",
        "readmission_30d_flag": "30-Day Readmission (Yes)",
        "jci_accredited": "JCI Hospital Accreditation",
        "intl_patient_desk": "Dedicated Intl. Patient Desk",
        "clinical_complexity_score": "Procedure Complexity (1–5)",
        "comorbidity_index": "Patient Comorbidity Index",
    }

    labels = [pretty_names.get(c["feature"], c["feature"]) for c in coefs]
    std_betas = [c["std_beta"] for c in coefs]
    colors = [TEAL if b > 0 else CORAL for b in std_betas]

    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    y = np.arange(len(labels))
    ax.barh(y, std_betas, color=colors, height=0.56)
    ax.axvline(0, color=NAVY, linewidth=1.1)

    for i, c in enumerate(coefs):
        b = c["std_beta"]
        sig = "***" if c["p_value"] < 0.001 else "**" if c["p_value"] < 0.01 else "*" if c["p_value"] < 0.05 else "ns"
        offset = 0.018 if b >= 0 else -0.018
        ha = "left" if b >= 0 else "right"
        ax.text(
            b + offset, i,
            f"β = {b:+.3f} (raw: {c['coef']:+.3f}) {sig}",
            va="center", ha=ha, fontsize=9, fontweight="bold", color=NAVY,
        )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontweight="bold")
    ax.set_xlabel("Standardized Effect Size (Standardized Beta Coefficient)")
    ax.set_title(
        f"Statistical Drivers of Patient Satisfaction\n(OLS Multiple Regression, R² = {sat_model['r_squared']:.3f}, n = {sat_model['n_obs']:,})",
        color=NAVY, pad=12, fontsize=12.5,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="x", alpha=0.8)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.98, 0.62)

    fig.text(
        0.015, 0.012,
        "Significance codes: *** p < 0.001, ** p < 0.01, * p < 0.05, ns = not significant. Estimated on non-imputed satisfaction survey responses.",
        fontsize=8.3, color=SLATE,
    )
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(FIG_DIR / "06_regression_drivers_satisfaction.png", dpi=200)
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    stats_data = json.loads(STATS_JSON.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    try:
        fig_01_corridors_and_savings(conn)
        fig_02_hospital_quadrant(conn)
        fig_03_jci_outcomes_ci(stats_data)
        fig_04_monthly_trends(conn)
        fig_05_worldbank_macro(conn)
        fig_06_regression_drivers(stats_data)
    finally:
        conn.close()
    print(f"Generated 6 executive charts in {FIG_DIR}")


if __name__ == "__main__":
    main()
