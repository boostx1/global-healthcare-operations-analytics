"""End-to-end reproducible runner for Global Healthcare Operations & Medical Tourism Analytics.

Usage:
    python src/run_all.py                    # Run full pipeline using cached World Bank CSV
    python src/run_all.py --refresh-worldbank # Re-fetch live World Bank Open Data API first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import build_dashboard
import build_excel_workbook
import etl_pipeline
import fetch_worldbank
import generate_raw_hospital_data
import generate_visuals
import statistical_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full healthcare analytics pipeline.")
    parser.add_argument(
        "--refresh-worldbank",
        action="store_true",
        help="Re-fetch official World Bank Open Data API indicators before ETL.",
    )
    args = parser.parse_args()

    wb_csv = SRC_DIR.parent / "data" / "raw" / "worldbank_health_indicators.csv"
    if args.refresh_worldbank or not wb_csv.exists():
        print("[1/6] Fetching official World Bank Open Data API indicators...")
        fetch_worldbank.main()
    else:
        print("[1/6] Using verified World Bank Open Data snapshot (pass --refresh-worldbank to re-fetch).")

    print("[2/6] Generating synthetic HIPAA/GDPR-safe multi-source hospital feeds...")
    generate_raw_hospital_data.main()

    print("[3/6] Running multi-source ETL cleaning, DQ audit & SQLite Star-Schema build...")
    etl_pipeline.run_etl()

    print("[4/6] Running statistical inference & OLS regression suite...")
    statistical_analysis.run_statistical_suite()

    print("[5/6] Generating 6 publication-quality figures...")
    generate_visuals.main()

    print("[6/6] Building formula-driven Excel workbook & interactive HTML BI dashboard...")
    build_excel_workbook.build_workbook()
    build_dashboard.build_dashboard()

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
