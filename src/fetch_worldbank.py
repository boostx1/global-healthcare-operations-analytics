"""Fetch real public macro-healthcare indicators from the World Bank Open Data API v2.

Countries covered (major medical tourism destinations and patient-origin markets):
- ARE: United Arab Emirates
- SWE: Sweden
- DEU: Germany
- TUR: Turkiye
- THA: Thailand
- IND: India
- SGP: Singapore
- USA: United States
"""

from __future__ import annotations

import csv
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

COUNTRIES = {
    "ARE": "United Arab Emirates",
    "SWE": "Sweden",
    "DEU": "Germany",
    "TUR": "Turkey",
    "THA": "Thailand",
    "IND": "India",
    "SGP": "Singapore",
    "USA": "United States",
}

INDICATORS = {
    "SH.MED.BEDS.ZS": "hospital_beds_per_1000",
    "SH.MED.PHYS.ZS": "physicians_per_1000",
    "SH.XPD.CHEX.PC.CD": "health_spend_per_capita_usd",
    "SH.XPD.CHEX.GD.ZS": "health_spend_pct_gdp",
    "SH.XPD.OOPC.CH.ZS": "out_of_pocket_pct_health_spend",
    "SP.DYN.LE00.IN": "life_expectancy_years",
    "SP.DYN.IMRT.IN": "infant_mortality_per_1000",
    "NY.GDP.PCAP.CD": "gdp_per_capita_usd",
}

YEAR_RANGE = "2015:2024"


def fetch_indicator(indicator_code: str, countries: list[str]) -> list[dict]:
    country_str = ";".join(countries)
    url = (
        f"https://api.worldbank.org/v2/country/{country_str}/indicator/{indicator_code}"
        f"?format=json&date={YEAR_RANGE}&per_page=1000"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "HealthcareOpsAnalytics/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return []
    return payload[1]


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    country_codes = list(COUNTRIES.keys())
    records: list[dict] = []
    metadata = {
        "source": "World Bank Open Data API v2",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "year_range": YEAR_RANGE,
        "countries": COUNTRIES,
        "indicators": INDICATORS,
        "indicator_counts": {},
    }

    for code, col_name in INDICATORS.items():
        rows = fetch_indicator(code, country_codes)
        non_null = 0
        for row in rows:
            iso3 = row.get("countryiso3code")
            if iso3 not in COUNTRIES:
                continue
            val = row.get("value")
            if val is not None:
                non_null += 1
            records.append(
                {
                    "country_code": iso3,
                    "country_name": COUNTRIES[iso3],
                    "year": int(row["date"]),
                    "indicator_code": code,
                    "indicator_name": col_name,
                    "value": "" if val is None else round(float(val), 4),
                }
            )
        metadata["indicator_counts"][col_name] = {
            "total_rows": len(rows),
            "non_null_rows": non_null,
            "missing_rows": len(rows) - non_null,
        }
        print(f"Fetched {code} ({col_name}): {non_null}/{len(rows)} non-null observations")

    out_csv = RAW_DIR / "worldbank_health_indicators.csv"
    records.sort(key=lambda r: (r["country_code"], r["indicator_code"], r["year"]))
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "country_code",
                "country_name",
                "year",
                "indicator_code",
                "indicator_name",
                "value",
            ],
        )
        writer.writeheader()
        writer.writerows(records)

    meta_path = RAW_DIR / "worldbank_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(records)} rows to {out_csv}")


if __name__ == "__main__":
    main()
