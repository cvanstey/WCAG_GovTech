"""
Master Appendix Merge Script.

Combines the three independently-generated compliance datasets into one
canonical table for the paper's appendix, while keeping the Adobe Acrobat
output separate as a cross-validation reference (not summed into totals,
since it duplicates the pypdf structural findings for NJLM_State_Magazine).

Run AFTER:
    - compliance_engine.py
    - multi_tier_eval.py
    - adobe_parsing.py
"""

import os
import pandas as pd

from pipeline_config import (
    DATA_DIR, OUTPUT_DIR, asset_path, output_path,
    NJLM_STATE_MAGAZINE_PDF, FEDERAL_GPO_REGISTER_PDF,
    log_start, log_complete,
)

# The three pypdf structural checks (Tagged/MarkInfo, Lang, Title) are a
# NARROW SUBSET of what Adobe Acrobat's full checker tests (23 rules total).
# Comparing Adobe's full failure total against pypdf's total was always an
# apples-to-oranges comparison; these are the specific Adobe rule IDs
# (as produced by adobe_parsing.py's slug: lowercase, spaces -> hyphens,
# "pdf-" prefix) that correspond 1:1 to what pypdf actually checks.
PYPDF_OVERLAPPING_ADOBE_CRITERIA = {
    "pdf-tagged-pdf",         # <-> pypdf's 1.3.1 /MarkInfo /Marked check
    "pdf-primary-language",   # <-> pypdf's 3.1.1 /Lang check
    "pdf-title",              # <-> pypdf's 2.4.2 title metadata check
}

# FIX: OUTPUT_DIR used to be redefined locally here as a bare relative
# "output" string, separate from pipeline_config.OUTPUT_DIR (which is
# anchored to PROJECT_ROOT). That's exactly the kind of per-script copy
# pipeline_config.py's docstring says it exists to eliminate — it was just
# never applied to output paths, only to input asset filenames. Now
# imported directly from pipeline_config so it can't drift.
#
# FIX: REQUIRED_INPUTS previously pointed at bare relative filenames.
# nj_govtech_compliance_matrix.csv and adobe_parsed_metrics.csv are written
# to cwd by compliance_engine.py / adobe_parsing.py respectively, so those
# happened to match if merge.py was run from the same cwd. But
# multi_tier_eval.py writes extended_document_compliance_matrix.csv via
# output_path(), i.e. to OUTPUT_DIR (<PROJECT_ROOT>/output/) regardless of
# cwd — so the old bare-relative lookup here would raise FileNotFoundError
# unless merge.py happened to be launched with cwd == OUTPUT_DIR. All three
# are now resolved through output_path() so every script agrees on where
# these files live no matter which directory it's launched from.
REQUIRED_INPUTS = {
    "Web DOM scan results": output_path("nj_govtech_compliance_matrix.csv"),
    "PDF structural check results": output_path("extended_document_compliance_matrix.csv"),
    "Adobe Acrobat validation results": output_path("adobe_parsed_metrics.csv"),
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
}


def load_required_csv(label: str, file_path: str) -> pd.DataFrame:
    """Load a required CSV or fail with a clear error."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"[MISSING INPUT] {label} not found at '{file_path}'. "
            f"Run the upstream script that generates this file first."
        )

    return pd.read_csv(file_path)


def validate_columns(df: pd.DataFrame, expected: set, label: str):
    """Verify that all expected columns exist."""
    missing = expected - set(df.columns)

    if missing:
        raise ValueError(
            f"[SCHEMA ERROR] {label} is missing required columns:\n"
            f"    {sorted(missing)}"
        )


def ensure_numeric(df: pd.DataFrame, columns: list[str], label: str):
    """Ensure numeric columns are actually numeric."""
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
    log_start("merge.py")  # FIX: was mistakenly logging "multi_tier_eval.py" (copy-paste leftover)
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

        adobe_validation = load_required_csv(
            "Adobe Acrobat validation results",
            REQUIRED_INPUTS["Adobe Acrobat validation results"],
        )

    except FileNotFoundError as exc:
        print(f"\n{exc}")
        raise SystemExit(1)

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

    validate_columns(
        adobe_validation,
        REQUIRED_COLUMNS["adobe_parsed_metrics.csv"],
        "Adobe Acrobat validation results",
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

    ensure_numeric(
        adobe_validation,
        ["Litigation_Risk_Weight"],
        "Adobe Acrobat validation results",
    )

    # ----------------------------
    # Create output directory
    # ----------------------------

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ----------------------------
    # Canonical appendix
    # ----------------------------

    master_appendix = (
        pd.concat(
            [web_matrix, document_matrix],
            ignore_index=True,
        )
        .sort_values(
            ["GovTech_Vendor", "Severity_Impact"],
            ignore_index=True,
        )
    )

    master_output = os.path.join(
        OUTPUT_DIR,
        "master_appendix.csv",
    )

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
    # Adobe validation reference
    # ----------------------------

    adobe_output = os.path.join(
        OUTPUT_DIR,
        "adobe_validation_reference.csv",
    )

    adobe_validation.to_csv(adobe_output, index=False)

    print("\n[VALIDATION REFERENCE]")
    print("Adobe Acrobat results are NOT included in master totals.")

    print(
        adobe_validation[
            [
                "WCAG_Success_Criterion",
                "Severity_Impact",
                "Litigation_Risk_Weight",
            ]
        ]
    )

    # Normalize whitespace before comparing, since a stray leading/trailing
    # space in either source file would silently zero out a match below.
    normalized_municipal_code = adobe_validation["Municipal_Code"].str.strip()
    adobe_all_rows = adobe_validation[normalized_municipal_code == NJLM_STATE_MAGAZINE_PDF]

    # FIX: Adobe's full checker tests ~23 rules; pypdf only tests 3
    # structural properties (tagged/lang/title). Comparing FULL totals
    # was comparing a comprehensive audit against a narrow one and would
    # always disagree — that's not a validation failure, it's a scope
    # mismatch. Restrict the Adobe side to just the 3 overlapping rules
    # before comparing, so this is a genuine apples-to-apples check.
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

    # A bare `adobe_weight == pypdf_weight` check is a false positive if the
    # join key (Municipal_Code / GovTech_Vendor) failed to match anything on
    # EITHER side — both totals default to 0 and look like agreement even
    # though nothing was actually cross-validated. Catch that case explicitly.
    if adobe_rows.empty or pypdf_rows.empty:
        print(
            "⚠ WARNING: No rows matched on one or both sides of the "
            "cross-validation join — nothing was actually compared. "
            f"(adobe_rows={len(adobe_rows)}, pypdf_rows={len(pypdf_rows)}). "
            "Check that Municipal_Code / GovTech_Vendor values line up "
            "with pipeline_config filenames, and that PYPDF_OVERLAPPING_ADOBE_CRITERIA "
            "matches the rule-name slugs adobe_parsing.py actually produces."
        )
    elif adobe_weight == pypdf_weight:
        print("✓ Adobe validation matches pypdf structural findings (on overlapping rules).")
    else:
        print(
            "⚠ WARNING: Adobe and pypdf totals differ even on the overlapping "
            "rule subset. Review the parsed findings — this IS a real discrepancy."
        )



    print("\nOutput files")
    print("-" * 40)
    print(master_output)
    print(adobe_output)

    print("\nMerge completed successfully.")

    summary = pd.DataFrame({
        "Metric": [
            "Rows",
            "Total Defect Nodes",
            "Total Litigation Weight",
            "Adobe Validation Weight",
            "pypdf Validation Weight",
        ],
        "Value": [
            len(master_appendix),
            master_appendix["Defect_Node_Count"].sum(),
            master_appendix["Litigation_Risk_Weight"].sum(),
            adobe_weight,
            pypdf_weight,
        ],
    })

    summary.to_csv(
        os.path.join(OUTPUT_DIR, "appendix_summary.csv"),
        index=False,
    )

    log_complete("merge.py")