"""
Master Appendix Merge Script.

Combines the three independently-generated compliance datasets into one
canonical table for the paper's appendix. Adobe Acrobat's output, if
present, is kept separate as an OPTIONAL cross-validation reference (not
summed into totals, since it duplicates the pypdf structural findings for
NJLM_State_Magazine). If you don't have Adobe Acrobat Pro, this step is
skipped automatically -- master_appendix.csv does not depend on it.

Run AFTER:
    - compliance_engine.py
    - multi_tier_eval.py
    - adobe_parsing.py (OPTIONAL -- only if you have Adobe Acrobat Pro)
"""

import os
import pandas as pd

from pipeline_config import (
    DATA_DIR, OUTPUT_DIR, asset_path, output_path,
    NJLM_STATE_MAGAZINE_PDF, FEDERAL_GPO_REGISTER_PDF,
    log_start, log_complete,
)
from remediation_guide import enrich_dataframe

PYPDF_OVERLAPPING_ADOBE_CRITERIA = {
    "pdf-tagged-pdf",
    "pdf-primary-language",
    "pdf-title",
}

REQUIRED_INPUTS = {
    "Web DOM scan results": output_path("nj_govtech_compliance_matrix.csv"),
    "PDF structural check results": output_path("extended_document_compliance_matrix.csv"),
}

# CHANGE: Adobe's file moved out of REQUIRED_INPUTS into its own optional
# lookup below, since merge.py should be able to produce master_appendix.csv
# without it.
#
# CHANGE: Lighthouse's page-scan results added as a second optional input,
# via lighthouse_to_dataframe.py's bridge output. Optional (not required)
# for the same reason Adobe is: lighthouse.py/lighthouse_to_dataframe.py
# require Node.js + Chrome and a manual scan run, so master_appendix.csv
# must still build without it if that step hasn't been run yet.
OPTIONAL_INPUTS = {
    "Adobe Acrobat validation results": output_path("adobe_parsed_metrics.csv"),
    "Lighthouse page-scan results": output_path("lighthouse_compliance_matrix.csv"),
}

REQUIRED_COLUMNS = {
    "nj_govtech_compliance_matrix.csv": {
        "GovTech_Vendor",
        "Severity_Impact",
        "Defect_Node_Count",
        "Litigation_Risk_Weight",
    },
    "extended_document_compliance_matrix.csv": {
        "GovTech_Vendor",
        "Severity_Impact",
        "Defect_Node_Count",
        "Litigation_Risk_Weight",
    },
    "adobe_parsed_metrics.csv": {
        "WCAG_Success_Criterion",
        "Severity_Impact",
        "Litigation_Risk_Weight",
    },
    "lighthouse_compliance_matrix.csv": {
        "GovTech_Vendor",
        "Severity_Impact",
        "Defect_Node_Count",
        "Litigation_Risk_Weight",
    },
}


def load_required_csv(label: str, file_path: str) -> pd.DataFrame:
    """Load a required CSV or fail with a clear error."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"[MISSING INPUT] {label} not found at '{file_path}'. "
            f"Run the upstream script that generates this file first."
        )
    return pd.read_csv(file_path)


def load_optional_csv(label: str, file_path: str) -> pd.DataFrame | None:
    """Load an optional CSV. Returns None (not an error) if missing."""
    if not os.path.exists(file_path):
        return None
    return pd.read_csv(file_path)


def validate_columns(df: pd.DataFrame, expected: set, label: str):
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(
            f"[SCHEMA ERROR] {label} is missing required columns:\n"
            f"    {sorted(missing)}"
        )


def ensure_numeric(df: pd.DataFrame, columns: list[str], label: str):
    for column in columns:
        if column not in df.columns:
            continue
        try:
            df[column] = pd.to_numeric(df[column], errors="raise")
        except Exception as exc:
            raise ValueError(
                f"[DATA ERROR] {label}: column '{column}' contains "
                f"non-numeric values."
            ) from exc


if __name__ == "__main__":
    log_start("merge.py")
    print("[MERGE PIPELINE] Checking required input files...")

    try:
        web_matrix = load_required_csv(
            "Web DOM scan results",
            REQUIRED_INPUTS["Web DOM scan results"],
        )

        document_matrix = load_required_csv(
            "PDF structural check results",
            REQUIRED_INPUTS["PDF structural check results"],
        )

    except FileNotFoundError as exc:
        print(f"\n{exc}")
        raise SystemExit(1)

    # CHANGE: Adobe load is now optional. have_adobe gates every
    # Adobe-specific block below instead of the script exiting outright.
    print("\n[OPTIONAL] Checking for Adobe Acrobat validation results...")
    adobe_validation = load_optional_csv(
        "Adobe Acrobat validation results",
        OPTIONAL_INPUTS["Adobe Acrobat validation results"],
    )
    have_adobe = adobe_validation is not None

    if have_adobe:
        print(f"[FOUND] {OPTIONAL_INPUTS['Adobe Acrobat validation results']}")
    else:
        print(
            "[INFO] No Adobe Acrobat validation file found — proceeding "
            "without cross-validation. This does not affect "
            "master_appendix.csv; Adobe's output was only ever a reference "
            "check, never part of the totals."
        )

    print("\n[OPTIONAL] Checking for Lighthouse page-scan results...")
    lighthouse_matrix = load_optional_csv(
        "Lighthouse page-scan results",
        OPTIONAL_INPUTS["Lighthouse page-scan results"],
    )
    have_lighthouse = lighthouse_matrix is not None

    if have_lighthouse:
        print(f"[FOUND] {OPTIONAL_INPUTS['Lighthouse page-scan results']}")
    else:
        print(
            "[INFO] No Lighthouse page-scan file found — proceeding without "
            "it. Run lighthouse.py then lighthouse_to_dataframe.py against "
            "crawled_targets.yaml to include every crawled page, not just "
            "the axe-core spot-checked endpoints."
        )

    # ----------------------------
    # Validate schemas
    # ----------------------------

    validate_columns(
        web_matrix,
        REQUIRED_COLUMNS["nj_govtech_compliance_matrix.csv"],
        "Web DOM scan results",
    )

    validate_columns(
        document_matrix,
        REQUIRED_COLUMNS["extended_document_compliance_matrix.csv"],
        "PDF structural check results",
    )

    # CHANGE: only validate Adobe's schema if the file was actually found
    if have_adobe:
        validate_columns(
            adobe_validation,
            REQUIRED_COLUMNS["adobe_parsed_metrics.csv"],
            "Adobe Acrobat validation results",
        )

    if have_lighthouse:
        validate_columns(
            lighthouse_matrix,
            REQUIRED_COLUMNS["lighthouse_compliance_matrix.csv"],
            "Lighthouse page-scan results",
        )

    # ----------------------------
    # Validate numeric fields
    # ----------------------------

    ensure_numeric(
        web_matrix,
        ["Defect_Node_Count", "Litigation_Risk_Weight"],
        "Web DOM scan results",
    )

    ensure_numeric(
        document_matrix,
        ["Defect_Node_Count", "Litigation_Risk_Weight"],
        "PDF structural check results",
    )

    # CHANGE: guarded
    if have_adobe:
        ensure_numeric(
            adobe_validation,
            ["Litigation_Risk_Weight"],
            "Adobe Acrobat validation results",
        )

    if have_lighthouse:
        ensure_numeric(
            lighthouse_matrix,
            ["Defect_Node_Count", "Litigation_Risk_Weight"],
            "Lighthouse page-scan results",
        )

    # ----------------------------
    # Create output directory
    # ----------------------------

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ----------------------------
    # Canonical appendix
    # ----------------------------

    # CHANGE: lighthouse_matrix folds in here too when present, right
    # alongside web_matrix (axe) and document_matrix (PDFs). This is the
    # fix for lighthouse.py's page-scan results otherwise dead-ending in
    # lighthouse_results.json and never reaching the reader-facing
    # appendix/remediation table.
    frames_to_merge = [web_matrix, document_matrix]
    if have_lighthouse:
        frames_to_merge.append(lighthouse_matrix)

    master_appendix = (
        pd.concat(
            frames_to_merge,
            ignore_index=True,
        )
        .sort_values(
            ["GovTech_Vendor", "Severity_Impact"],
            ignore_index=True,
        )
    )

    # CHANGE: enrich with plain-language explanation / responsible party /
    # fix steps before writing out, so the appendix is self-explanatory.
    master_appendix = enrich_dataframe(master_appendix)

    master_output = os.path.join(OUTPUT_DIR, "master_appendix.csv")
    master_appendix.to_csv(master_output, index=False)

    print("\n[MASTER APPENDIX GENERATED]")
    print(master_appendix.groupby(
        ["GovTech_Vendor", "Severity_Impact"]
    )["Defect_Node_Count"].sum())

    print("\nSummary")
    print("-" * 40)
    print(f"Rows: {len(master_appendix)}")
    print(f"Total Defect Nodes: {master_appendix['Defect_Node_Count'].sum()}")
    print(
        f"Total Litigation Weight: "
        f"{master_appendix['Litigation_Risk_Weight'].sum()}"
    )

    # ----------------------------
    # Adobe validation reference (OPTIONAL — entire block skipped if absent)
    # ----------------------------

    adobe_weight = None
    pypdf_weight = None

    if have_adobe:
        adobe_output = os.path.join(OUTPUT_DIR, "adobe_validation_reference.csv")
        adobe_validation.to_csv(adobe_output, index=False)

        print("\n[VALIDATION REFERENCE]")
        print("Adobe Acrobat results are NOT included in master totals.")
        print(
            adobe_validation[
                ["WCAG_Success_Criterion", "Severity_Impact", "Litigation_Risk_Weight"]
            ]
        )

        normalized_municipal_code = adobe_validation["Municipal_Code"].str.strip()
        adobe_all_rows = adobe_validation[normalized_municipal_code == NJLM_STATE_MAGAZINE_PDF]

        adobe_rows = adobe_all_rows[
            adobe_all_rows["WCAG_Success_Criterion"].isin(PYPDF_OVERLAPPING_ADOBE_CRITERIA)
        ]
        adobe_weight = adobe_rows["Litigation_Risk_Weight"].sum()

        pypdf_rows = document_matrix[document_matrix["GovTech_Vendor"] == "NJLM_State_Magazine"]
        pypdf_weight = pypdf_rows["Litigation_Risk_Weight"].sum()

        print("\nValidation Totals (restricted to the 3 rules both tools test)")
        print("-" * 40)
        print(
            f"Adobe Subset Weight : {adobe_weight}  "
            f"({len(adobe_rows)}/{len(adobe_all_rows)} Adobe rows in scope)"
        )
        print(f"pypdf Total Weight  : {pypdf_weight}  ({len(pypdf_rows)} rows matched)")
        if len(adobe_all_rows) > len(adobe_rows):
            print(
                f"Note: Adobe also flagged {len(adobe_all_rows) - len(adobe_rows)} "
                "additional failed rule(s) outside pypdf's structural scope "
                "(e.g. tab order, alt text) — expected, not a discrepancy."
            )

        if adobe_rows.empty or pypdf_rows.empty:
            print(
                "⚠ WARNING: No rows matched on one or both sides of the "
                "cross-validation join — nothing was actually compared. "
                f"(adobe_rows={len(adobe_rows)}, pypdf_rows={len(pypdf_rows)}). "
                "Check that Municipal_Code / GovTech_Vendor values line up "
                "with pipeline_config filenames, and that "
                "PYPDF_OVERLAPPING_ADOBE_CRITERIA matches the rule-name "
                "slugs adobe_parsing.py actually produces."
            )
        elif adobe_weight == pypdf_weight:
            print("✓ Adobe validation matches pypdf structural findings (on overlapping rules).")
        else:
            print(
                "⚠ WARNING: Adobe and pypdf totals differ even on the overlapping "
                "rule subset. Review the parsed findings — this IS a real discrepancy."
            )
    else:
        print("\n[VALIDATION REFERENCE]")
        print("Skipped — no Adobe Acrobat validation file present.")

    print("\nOutput files")
    print("-" * 40)
    print(master_output)
    if have_adobe:
        print(os.path.join(OUTPUT_DIR, "adobe_validation_reference.csv"))

    print("\nMerge completed successfully.")

    # CHANGE: summary CSV now includes Adobe/pypdf rows only when available,
    # instead of crashing on undefined adobe_weight/pypdf_weight.
    summary_metrics = ["Rows", "Total Defect Nodes", "Total Litigation Weight"]
    summary_values = [
        len(master_appendix),
        master_appendix["Defect_Node_Count"].sum(),
        master_appendix["Litigation_Risk_Weight"].sum(),
    ]

    if have_adobe:
        summary_metrics += ["Adobe Validation Weight", "pypdf Validation Weight"]
        summary_values += [adobe_weight, pypdf_weight]

    summary = pd.DataFrame({"Metric": summary_metrics, "Value": summary_values})
    summary.to_csv(os.path.join(OUTPUT_DIR, "appendix_summary.csv"), index=False)

    log_complete("merge.py")