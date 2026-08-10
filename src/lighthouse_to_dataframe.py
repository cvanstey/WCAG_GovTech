"""
lighthouse_to_dataframe.py

Bridges lighthouse.py's per-page scan output into the same flat row
schema compliance_engine.py produces (nj_govtech_compliance_matrix.csv),
so Lighthouse's "every crawled page" results actually reach
master_appendix.csv instead of dead-ending in lighthouse_results.json.

Run AFTER:
    - crawler.py           (produces crawled_targets.yaml)
    - lighthouse.py         (produces lighthouse_results.json)

Feeds INTO:
    - merges01.py           (via lighthouse_compliance_matrix.csv, optional input)

--- Modeling assumptions (read before trusting the numbers) ---

axe-core (compliance_engine.py) reports an actual DOM node count per
violation and an explicit `impact` severity (critical/serious/moderate/
minor). Lighthouse's accessibility audits are page-level pass/fail with
NEITHER of those:

  * Defect_Node_Count -- Lighthouse gives no node count, so this counts
    1 defect per FAILED AUDIT per page. It is not a real element count
    and is not directly comparable to axe's Defect_Node_Count -- it's a
    per-audit tally, not a per-node one.

  * Severity_Impact -- Lighthouse gives no impact rating, so this is
    DERIVED from the WCAG conformance level already present in
    lighthouse.py's WCAG_MAPPING (Level A / AA):
        Level A   -> "critical"  (minimum conformance failures)
        Level AA  -> "serious"
        unmapped  -> "moderate"
    This is a stated policy choice, not a measurement -- disclose it
    as such in any methodology write-up, the same way the "1 per
    failed audit" node-count convention should be disclosed.

  * WCAG_Success_Criterion is populated with the Lighthouse AUDIT ID
    (e.g. "color-contrast", "heading-order"), matching the convention
    compliance_engine.py already uses and what remediation_guide.py's
    lookup table is keyed on -- several Lighthouse audit ids are shared
    axe-core rule ids, so existing remediation_guide.py entries apply
    directly without new mapping work.
"""

import json
import os
from typing import Dict, List, Optional

import pandas as pd

from pipeline_config import output_path, log_start, log_complete
from compliance_engine import SEVERITY_WEIGHTS  # single source of truth, not a 3rd copy

DEFAULT_LIGHTHOUSE_JSON = output_path("lighthouse_results.json")
DEFAULT_OUT_CSV = output_path("lighthouse_compliance_matrix.csv")

LEVEL_TO_SEVERITY = {
    "A": "critical",
    "AA": "serious",
}
DEFAULT_SEVERITY = "moderate"


def _severity_for_level(level: Optional[str]) -> str:
    return LEVEL_TO_SEVERITY.get(level, DEFAULT_SEVERITY)


def lighthouse_to_dataframe(json_path: str = DEFAULT_LIGHTHOUSE_JSON) -> pd.DataFrame:
    """
    Reads lighthouse.py's --out JSON (a list of LighthouseResult dicts) and
    flattens every FAILED accessibility audit on every successfully-scanned
    page into one row per (page, failed audit) -- matching the same
    Defect_Node_Count / Severity_Impact / Litigation_Risk_Weight schema
    compliance_engine.py's transform_violations_to_dataframe() produces.

    Pages that errored during the scan (result["error"] set) are skipped
    entirely -- an error is not a zero-violation result and must not be
    silently counted as "passed", same convention as multi_tier_eval.py's
    non-200 handling.
    """
    if not os.path.exists(json_path):
        print(f"[FILE ALERT] Lighthouse results JSON missing from local path: {json_path}")
        return pd.DataFrame()

    with open(json_path, "r", encoding="utf-8") as f:
        results: List[Dict] = json.load(f)

    records: List[Dict] = []
    skipped_errors = 0

    for page_result in results:
        if page_result.get("error"):
            skipped_errors += 1
            continue

        municipality = page_result.get("municipality", "Unlabeled_Municipality")
        platform = page_result.get("platform", "Unlabeled_Platform")
        url = page_result.get("url")

        for issue in page_result.get("critical_a11y_issues", []):
            wcag_level = issue.get("wcag_level")
            severity = _severity_for_level(wcag_level)

            records.append({
                "DSSA_Timestamp": pd.Timestamp.now(),
                "GovTech_Vendor": platform,
                "Municipal_Code": municipality,
                "Source_URL": url,
                "WCAG_Success_Criterion": issue.get("id", "unknown-rule"),
                "WCAG_SC_Number": issue.get("wcag_sc", "Unmapped"),
                "Severity_Impact": severity,
                "Defect_Node_Count": 1,  # see module docstring: per-audit, not per-node
                "Litigation_Risk_Weight": SEVERITY_WEIGHTS.get(severity, 2),
            })

    if skipped_errors:
        print(
            f"[LIGHTHOUSE BRIDGE] Skipped {skipped_errors} page(s) that "
            f"errored during scanning (not counted as passing)."
        )

    return pd.DataFrame(records)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert lighthouse.py JSON output into the shared compliance-matrix CSV schema."
    )
    parser.add_argument("--in", dest="json_path", default=DEFAULT_LIGHTHOUSE_JSON,
                         help="Path to lighthouse.py's --out JSON file")
    parser.add_argument("--out", dest="out_csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args()

    log_start("lighthouse_to_dataframe.py")

    print(f"[PROCESSING] Reading Lighthouse scan results from {args.json_path} ...")
    lighthouse_matrix = lighthouse_to_dataframe(args.json_path)

    if lighthouse_matrix.empty:
        print("[PIPELINE ALERT] No failed-audit rows produced -- check the JSON path "
              "and confirm lighthouse.py actually recorded any failed accessibility audits.")
    else:
        lighthouse_matrix.to_csv(args.out_csv, index=False)
        print(f"\n[SUCCESS] Wrote {len(lighthouse_matrix)} rows to {args.out_csv}")
        print(
            lighthouse_matrix.groupby(
                ["GovTech_Vendor", "Severity_Impact"]
            )["Defect_Node_Count"].sum()
        )

    log_complete("lighthouse_to_dataframe.py")