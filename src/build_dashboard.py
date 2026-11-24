"""Build a self-contained, interactive executive BI dashboard (dashboard/index.html)
that renders directly in any modern browser or GitHub Pages with live filtering
by destination country, hospital tier, and JCI accreditation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "healthcare_ops.db"
STATS_JSON = BASE_DIR / "reports" / "statistical_results.json"
OUT_HTML = BASE_DIR / "dashboard" / "index.html"


def build_dashboard() -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        hospitals = pd.read_sql_query("SELECT * FROM vw_hospital_scorecard ORDER BY quality_rank", conn).to_dict(orient="records")
        corridors = pd.read_sql_query("SELECT * FROM vw_medical_tourism_corridors LIMIT 20", conn).to_dict(orient="records")
        monthly = pd.read_sql_query("SELECT * FROM vw_monthly_operations_kpi", conn).to_dict(orient="records")
        macro = pd.read_sql_query("SELECT * FROM vw_country_macro_vs_ops", conn).to_dict(orient="records")
        audit = pd.read_sql_query("SELECT * FROM etl_data_quality_audit ORDER BY audit_id", conn).to_dict(orient="records")
    finally:
        conn.close()

    stats_data = json.loads(STATS_JSON.read_text(encoding="utf-8"))
    payload = {
        "hospitals": hospitals,
        "corridors": corridors,
        "monthly": monthly,
        "macro": macro,
        "audit": audit,
        "stats": {
            "jci_readm": stats_data["jci_readmission_test"],
            "jci_comp": stats_data["jci_complication_test"],
            "wait_test": stats_data["mt_vs_domestic_wait"],
            "ols_sat_r2": stats_data["ols_patient_satisfaction"]["r_squared"],
            "ols_los_r2": stats_data["ols_length_of_stay"]["r_squared"],
        },
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Global Healthcare Operations &amp; Medical Tourism BI Dashboard</title>
<style>
  :root {{
    --navy: #0F3D5E;
    --teal: #0D9488;
    --amber: #D97706;
    --coral: #DC2626;
    --bg: #F8FAFC;
    --card: #FFFFFF;
    --border: #E2E8F0;
    --text: #1E293B;
    --muted: #64748B;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  header {{
    background: linear-gradient(135deg, #0F3D5E 0%, #0D5C75 100%);
    color: #fff;
    padding: 26px 32px;
    border-bottom: 4px solid var(--teal);
  }}
  header h1 {{ font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; }}
  header p {{ color: #CBD5E1; font-size: 0.92rem; margin-top: 4px; }}
  .container {{ max-width: 1320px; margin: 0 auto; padding: 22px 24px 48px; }}
  .controls {{
    display: flex; flex-wrap: wrap; gap: 14px; align-items: end;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 18px; margin-bottom: 20px;
  }}
  .control-group {{ display: flex; flex-direction: column; gap: 4px; min-width: 180px; }}
  .control-group label {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--muted); }}
  .control-group select {{
    padding: 7px 10px; border: 1px solid #CBD5E1; border-radius: 6px;
    font-size: 0.9rem; background: #fff; color: var(--text);
  }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(195px, 1fr));
    gap: 14px; margin-bottom: 22px;
  }}
  .kpi-card {{
    background: var(--card); border: 1px solid var(--border);
    border-left: 4px solid var(--teal); border-radius: 10px; padding: 16px 18px;
  }}
  .kpi-label {{ font-size: 0.76rem; font-weight: 700; text-transform: uppercase; color: var(--muted); }}
  .kpi-value {{ font-size: 1.65rem; font-weight: 800; color: var(--navy); margin-top: 4px; }}
  .kpi-sub {{ font-size: 0.78rem; color: var(--muted); margin-top: 2px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1.25fr 1fr; gap: 18px; margin-bottom: 22px; }}
  @media (max-width: 960px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .panel {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;
  }}
  .panel h2 {{ font-size: 1.05rem; color: var(--navy); margin-bottom: 4px; }}
  .panel .sub {{ font-size: 0.82rem; color: var(--muted); margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
  th {{
    text-align: left; font-size: 0.75rem; text-transform: uppercase; color: var(--muted);
    border-bottom: 2px solid var(--border); padding: 9px 10px; background: #F8FAFC;
  }}
  td {{ padding: 9px 10px; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: #F1F5F9; }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 0.74rem; font-weight: 700;
  }}
  .badge-jci {{ background: #CCFBF1; color: #0F766E; }}
  .badge-non {{ background: #FEE2E2; color: #B91C1C; }}
  .bar-wrap {{ width: 100px; background: #E2E8F0; border-radius: 4px; height: 8px; display: inline-block; vertical-align: middle; margin-right: 6px; }}
  .bar-fill {{ height: 100%; border-radius: 4px; background: var(--teal); }}
  .stat-pill {{
    display: inline-block; background: #EFF6FF; border: 1px solid #BFDBFE;
    color: #1E40AF; border-radius: 6px; padding: 6px 10px; font-size: 0.82rem; margin: 4px 6px 4px 0;
  }}
  .table-scroll {{ overflow-x: auto; }}
  footer {{ text-align: center; font-size: 0.8rem; color: var(--muted); margin-top: 28px; }}
</style>
</head>
<body>
<header>
  <h1>Global Healthcare Operations &amp; Medical Tourism BI Dashboard</h1>
  <p>SQLite Star Schema (6,000 Clean Encounters, 24 Partner Hospitals) + Live World Bank Open Data Benchmarks &bull; Author: Subhi Alloush</p>
</header>

<div class="container">
  <div class="controls">
    <div class="control-group">
      <label for="fCountry">Destination Country</label>
      <select id="fCountry"><option value="ALL">All 8 Countries</option></select>
    </div>
    <div class="control-group">
      <label for="fJci">JCI Accreditation</label>
      <select id="fJci">
        <option value="ALL">All Hospitals</option>
        <option value="1">JCI Accredited Only</option>
        <option value="0">Non-JCI Only</option>
      </select>
    </div>
    <div class="control-group">
      <label for="fTier">Hospital Tier</label>
      <select id="fTier">
        <option value="ALL">All Tiers</option>
        <option value="Quaternary">Quaternary</option>
        <option value="Tertiary">Tertiary</option>
        <option value="Specialty Center">Specialty Center</option>
      </select>
    </div>
  </div>

  <div class="kpi-grid" id="kpiGrid"></div>

  <div class="grid-2">
    <div class="panel">
      <h2>Value-Based Care Quadrant (Quality Score vs. Avg Procedure Cost)</h2>
      <div class="sub">Hover any hospital bubble to inspect quality rank, cost, and readmission rate. Teal = JCI Accredited, Coral = Non-JCI.</div>
      <svg id="quadrantSvg" viewBox="0 0 640 340" style="width:100%;height:auto;"></svg>
    </div>
    <div class="panel">
      <h2>Inferential Statistics Highlights</h2>
      <div class="sub">Key validated findings from Python &amp; SciPy statistical testing (n = 6,000 encounters).</div>
      <div id="statsBox"></div>
      <h2 style="margin-top:16px;">Top Cross-Border Corridors</h2>
      <div class="sub">Highest-volume international patient flows and average net cost savings.</div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Origin &rarr; Destination</th><th>Cases</th><th>Avg Total</th><th>Net Savings</th></tr></thead>
          <tbody id="corridorBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>Partner Hospital Performance Scorecard</h2>
    <div class="sub">Filtered dynamically by Country, JCI Accreditation, and Tier. Composite Quality combines clinical outcomes (35%), low readmissions (25%), low complications (20%), and satisfaction (20%).</div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Rank</th><th>Hospital</th><th>Country</th><th>Tier</th><th>JCI</th>
            <th>Encounters</th><th>Avg Cost</th><th>Wait (d)</th><th>Readm %</th><th>Sat (1-5)</th><th>Quality Score</th>
          </tr>
        </thead>
        <tbody id="hospBody"></tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h2>Real-World Macro Health Benchmarks (World Bank Open Data API)</h2>
    <div class="sub">Official World Bank indicators joined to partner hospital network metrics (latest available non-null observation, 2015–2024).</div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Country</th><th>Health System</th><th>Health Spend/Capita</th><th>Out-of-Pocket %</th>
            <th>Beds / 1,000</th><th>Life Expectancy</th><th>Partner Avg Cost</th><th>Partner Readm %</th>
          </tr>
        </thead>
        <tbody id="macroBody"></tbody>
      </table>
    </div>
  </div>

  <footer>
    Global Healthcare Operations &amp; Medical Tourism Analytics &bull; HIPAA/GDPR-Safe Synthetic Clinical Operations + Official World Bank Open Data API v2
  </footer>
</div>

<script>
const DATA = {json.dumps(payload)};

const countrySel = document.getElementById("fCountry");
[...new Set(DATA.hospitals.map(h => h.country_name))].sort().forEach(c => {{
  const opt = document.createElement("option");
  opt.value = c; opt.textContent = c;
  countrySel.appendChild(opt);
}});

function fmtUSD(v) {{ return v == null ? "—" : "$" + Math.round(v).toLocaleString("en-US"); }}

function renderStats() {{
  const s = DATA.stats;
  document.getElementById("statsBox").innerHTML = `
    <div class="stat-pill"><strong>JCI Readmission RRR:</strong> ${{s.jci_readm.relative_risk_reduction_pct}}% (OR ${{s.jci_readm.odds_ratio}}, p=${{s.jci_readm.p_value.toExponential(1)}})</div>
    <div class="stat-pill"><strong>JCI Complication RRR:</strong> ${{s.jci_comp.relative_risk_reduction_pct}}% (OR ${{s.jci_comp.odds_ratio}}, p=${{s.jci_comp.p_value.toExponential(1)}})</div>
    <div class="stat-pill"><strong>Wait Time Advantage:</strong> Intl ${{s.wait_test.mt_mean_days}}d vs Domestic ${{s.wait_test.dom_mean_days}}d (p=${{s.wait_test.welch_p.toExponential(1)}})</div>
    <div class="stat-pill"><strong>OLS Models:</strong> Satisfaction R&sup2; = ${{(s.ols_sat_r2*100).toFixed(1)}}% &bull; LOS R&sup2; = ${{(s.ols_los_r2*100).toFixed(1)}}%</div>
  `;
}}

function renderStaticTables() {{
  document.getElementById("corridorBody").innerHTML = DATA.corridors.slice(0, 7).map(c => `
    <tr>
      <td><strong>${{c.origin_country_code}} &rarr; ${{c.destination_country}}</strong></td>
      <td>${{c.encounter_volume}}</td>
      <td>${{fmtUSD(c.avg_destination_total_usd)}}</td>
      <td style="font-weight:700;color:${{c.avg_net_savings_pct >= 0 ? '#0D9488' : '#DC2626'}}">${{c.avg_net_savings_pct >= 0 ? '+' : ''}}${{c.avg_net_savings_pct}}%</td>
    </tr>
  `).join("");

  document.getElementById("macroBody").innerHTML = DATA.macro.map(m => `
    <tr>
      <td><strong>${{m.country_name}}</strong></td>
      <td>${{m.health_system_model}}</td>
      <td>${{fmtUSD(m.wb_health_spend_pc_usd)}}</td>
      <td>${{m.wb_oop_pct_spend != null ? m.wb_oop_pct_spend.toFixed(1) + "%" : "—"}}</td>
      <td>${{m.wb_beds_per_1000 != null ? m.wb_beds_per_1000.toFixed(2) : "—"}}</td>
      <td>${{m.wb_life_expectancy != null ? m.wb_life_expectancy.toFixed(1) + " yrs" : "—"}}</td>
      <td>${{fmtUSD(m.avg_procedure_cost_usd)}}</td>
      <td>${{m.avg_readmission_rate_pct}}%</td>
    </tr>
  `).join("");
}}

function renderQuadrant(rows) {{
  const svg = document.getElementById("quadrantSvg");
  const W = 640, H = 340, padL = 54, padR = 24, padT = 20, padB = 42;
  const maxCost = Math.max(...DATA.hospitals.map(h => h.avg_procedure_cost_usd)) * 1.08;
  const minQual = Math.min(...DATA.hospitals.map(h => h.composite_quality_score)) - 2;
  const maxQual = Math.max(...DATA.hospitals.map(h => h.composite_quality_score)) + 2;
  const sx = c => padL + (c / maxCost) * (W - padL - padR);
  const sy = q => H - padB - ((q - minQual) / (maxQual - minQual)) * (H - padT - padB);

  const medCost = DATA.hospitals.map(h => h.avg_procedure_cost_usd).sort((a,b)=>a-b)[12];
  const medQual = DATA.hospitals.map(h => h.composite_quality_score).sort((a,b)=>a-b)[12];

  let out = `
    <rect x="${{padL}}" y="${{padT}}" width="${{sx(medCost)-padL}}" height="${{sy(medQual)-padT}}" fill="#CCFBF1" opacity="0.28"/>
    <line x1="${{sx(medCost)}}" y1="${{padT}}" x2="${{sx(medCost)}}" y2="${{H-padB}}" stroke="#94A3B8" stroke-dasharray="4 4"/>
    <line x1="${{padL}}" y1="${{sy(medQual)}}" x2="${{W-padR}}" y2="${{sy(medQual)}}" stroke="#94A3B8" stroke-dasharray="4 4"/>
    <line x1="${{padL}}" y1="${{H-padB}}" x2="${{W-padR}}" y2="${{H-padB}}" stroke="#CBD5E1"/>
    <line x1="${{padL}}" y1="${{padT}}" x2="${{padL}}" y2="${{H-padB}}" stroke="#CBD5E1"/>
    <text x="${{padL+6}}" y="${{padT+14}}" font-size="10" font-weight="700" fill="#0F766E">HIGH-VALUE LEADERS</text>
    <text x="${{(padL+W-padR)/2}}" y="${{H-8}}" text-anchor="middle" font-size="11" fill="#475569">Average Procedure Cost (USD)</text>
    <text x="14" y="${{(padT+H-padB)/2}}" text-anchor="middle" font-size="11" fill="#475569" transform="rotate(-90 14 ${{(padT+H-padB)/2}})">Composite Quality Score</text>
  `;
  for (let t = 0; t <= 4; t++) {{
    const cv = (maxCost / 4) * t;
    out += `<text x="${{sx(cv)}}" y="${{H-padB+15}}" text-anchor="middle" font-size="10" fill="#64748B">$${{Math.round(cv/1000)}}k</text>`;
    const qv = minQual + ((maxQual - minQual) / 4) * t;
    out += `<text x="${{padL-8}}" y="${{sy(qv)+3}}" text-anchor="end" font-size="10" fill="#64748B">${{qv.toFixed(0)}}</text>`;
  }}
  rows.forEach(h => {{
    const cx = sx(h.avg_procedure_cost_usd), cy = sy(h.composite_quality_score);
    const r = Math.max(6, Math.sqrt(h.total_encounters) * 0.65);
    const fill = h.jci_accredited ? "#0D9488" : "#DC2626";
    out += `<circle cx="${{cx}}" cy="${{cy}}" r="${{r}}" fill="${{fill}}" fill-opacity="0.82" stroke="#fff" stroke-width="1.4">
      <title>${{h.hospital_name}} (${{h.country_name}})&#10;Rank #${{h.quality_rank}} | Quality: ${{h.composite_quality_score}}&#10;Avg Cost: ${{fmtUSD(h.avg_procedure_cost_usd)}} | Readm: ${{h.readmission_rate_pct}}%</title>
    </circle>`;
  }});
  svg.innerHTML = out;
}}

function update() {{
  const cVal = document.getElementById("fCountry").value;
  const jVal = document.getElementById("fJci").value;
  const tVal = document.getElementById("fTier").value;

  const filtered = DATA.hospitals.filter(h =>
    (cVal === "ALL" || h.country_name === cVal) &&
    (jVal === "ALL" || String(h.jci_accredited) === jVal) &&
    (tVal === "ALL" || h.hospital_tier === tVal)
  );

  const totEnc = filtered.reduce((s, h) => s + h.total_encounters, 0);
  const intlEnc = filtered.reduce((s, h) => s + h.intl_encounters, 0);
  const wAvg = (fn) => totEnc ? filtered.reduce((s, h) => s + fn(h) * h.total_encounters, 0) / totEnc : 0;

  const kpis = [
    ["Partner Hospitals", filtered.length, `${{filtered.filter(h=>h.jci_accredited).length}} JCI accredited`],
    ["Clean Encounters", totEnc.toLocaleString("en-US"), `${{totEnc ? (100*intlEnc/totEnc).toFixed(1) : 0}}% medical tourists`],
    ["Avg Quality Score", wAvg(h=>h.composite_quality_score).toFixed(2), "Composite 0–100 index"],
    ["30-Day Readmission", wAvg(h=>h.readmission_rate_pct).toFixed(2) + "%", `Complications: ${{wAvg(h=>h.complication_rate_pct).toFixed(2)}}%`],
    ["Avg Wait Time", wAvg(h=>h.avg_wait_days).toFixed(1) + " days", `Avg LOS: ${{wAvg(h=>h.avg_los_days).toFixed(1)}} days`],
    ["Avg Procedure Cost", fmtUSD(wAvg(h=>h.avg_procedure_cost_usd)), `Avg Satisfaction: ${{wAvg(h=>h.avg_satisfaction).toFixed(2)}} / 5.0`],
  ];
  document.getElementById("kpiGrid").innerHTML = kpis.map(([l,v,s]) => `
    <div class="kpi-card">
      <div class="kpi-label">${{l}}</div>
      <div class="kpi-value">${{v}}</div>
      <div class="kpi-sub">${{s}}</div>
    </div>
  `).join("");

  document.getElementById("hospBody").innerHTML = filtered.map(h => `
    <tr>
      <td><strong>#${{h.quality_rank}}</strong></td>
      <td><strong>${{h.hospital_name}}</strong><br><span style="font-size:0.76rem;color:#64748B">${{h.city}}</span></td>
      <td>${{h.country_name}}</td>
      <td>${{h.hospital_tier}}</td>
      <td><span class="badge ${{h.jci_accredited ? 'badge-jci' : 'badge-non'}}">${{h.jci_accredited ? 'JCI' : 'Non-JCI'}}</span></td>
      <td>${{h.total_encounters}}</td>
      <td>${{fmtUSD(h.avg_procedure_cost_usd)}}</td>
      <td>${{h.avg_wait_days}}</td>
      <td>${{h.readmission_rate_pct}}%</td>
      <td>${{h.avg_satisfaction}}</td>
      <td><span class="bar-wrap"><span class="bar-fill" style="width:${{Math.min(100, h.composite_quality_score)}}%"></span></span><strong>${{h.composite_quality_score}}</strong></td>
    </tr>
  `).join("");

  renderQuadrant(filtered);
}}

["fCountry", "fJci", "fTier"].forEach(id => document.getElementById(id).addEventListener("change", update));
renderStats();
renderStaticTables();
update();
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Built interactive BI dashboard -> {OUT_HTML}")


if __name__ == "__main__":
    build_dashboard()
