"""
Adobe Acrobat Accessibility Report DOCX Parser.

Parses Adobe's exported Word (.docx) accessibility checker reports into
standard DSSA observation rows. Reads structured table cells directly
rather than plain-text substring matching, avoiding false positives from
summary-section text (e.g. "Failed: 1" bullet counts).
"""

import os
from typing import Dict, List
import pandas as pd
from docx import Document

from pipeline_config import (
    DATA_DIR, asset_path, output_path,
    NJLM_STATE_MAGAZINE_PDF, FEDERAL_GPO_REGISTER_PDF,
    NJLM_STATE_MAGAZINE_DOCX, FEDERAL_GPO_REGISTER_DOCX,
    log_start, log_complete,
)

def parse_adobe_docx_report(vendor_name: str, file_name: str, docx_path: str) -> pd.DataFrame:
    """
    Parses an Adobe Acrobat accessibility report exported as .docx.

    Each "Failed" rule is treated as ONE discrete accessibility defect.
    No structural inflation (e.g. page counts) is used in this model.
    """

    if not os.path.exists(docx_path):
        print(f"[FILE ALERT] Adobe DOCX report missing from local path: {docx_path}")
        return pd.DataFrame()

    doc = Document(docx_path)
    parsed_records: List[Dict] = []

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]

            if len(cells) < 2:
                continue

            rule_name, status = cells[0], cells[1]

            # Strict match avoids header contamination
            if status != "Failed":
                continue

            rule_identifier = rule_name.strip().replace(" ", "-").lower()
            if not rule_identifier:
                continue

            parsed_records.append({
                "DSSA_Timestamp": pd.Timestamp.now(),
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": file_name,
                "WCAG_Success_Criterion": f"pdf-{rule_identifier}",
                "Severity_Impact": "critical" if "tagged" in rule_identifier else "serious",

                # ✅ FIXED: consistent unit of measurement across pipeline
                "Defect_Node_Count": 1,

                # Risk remains weighted but independent of defect counting
                "Litigation_Risk_Weight": 10 if "tagged" in rule_identifier else 5
            })

    return pd.DataFrame(parsed_records)


# --- EXECUTION SWITCH ---
if __name__ == "__main__":
    from pipeline_config import DATA_DIR, asset_path, NJLM_STATE_MAGAZINE_PDF, PASSPORT_FORM_PDF, FEDERAL_GPO_REGISTER_PDF, \
        NJLM_STATE_MAGAZINE_DOCX, FEDERAL_GPO_REGISTER_DOCX, PASSPORT_FORM_DOCX

    reports = {
        "NJLM_State_Magazine": {
            "file_name": NJLM_STATE_MAGAZINE_PDF,
            "docx_path": asset_path(NJLM_STATE_MAGAZINE_DOCX),
        },
        "Federal_GPO_Register": {
            "file_name": FEDERAL_GPO_REGISTER_PDF,
            "docx_path": asset_path(FEDERAL_GPO_REGISTER_DOCX),
        },

        "Passport_Form": {
            "file_name": PASSPORT_FORM_PDF,
            "docx_path": asset_path(PASSPORT_FORM_DOCX)
        },
    }

    # FIX: log_start/log_complete were imported but never called anywhere
    # in this script, unlike multi_tier_eval.py and compliance_engine.py.
    log_start("adobe_parsing.py")

    print("[PROCESSING] Ingesting Adobe Acrobat DOCX report exports...")

    all_frames: List[pd.DataFrame] = []

    for vendor_name, info in reports.items():
        frame = parse_adobe_docx_report(
            vendor_name,
            info["file_name"],
            info["docx_path"]
        )

        if frame.empty:
            print(f"[WARNING] No 'Failed' rules parsed for {vendor_name} — check DOCX structure or path.")

        all_frames.append(frame)

    if any(not f.empty for f in all_frames):
        adobe_data_frame = pd.concat(all_frames, ignore_index=True)

        print("\n[SUCCESS] Adobe dataset integrated successfully:")
        print(adobe_data_frame[[
            "GovTech_Vendor",
            "WCAG_Success_Criterion",
            "Severity_Impact",
            "Litigation_Risk_Weight"
        ]])

        # FIX: was writing to a bare relative "adobe_parsed_metrics.csv"
        # (i.e. wherever this script's cwd happened to be), while
        # merge.py now looks for it under pipeline_config.OUTPUT_DIR
        # (<PROJECT_ROOT>/output/). Routed through output_path() so it
        # lands in the same place regardless of launch directory.
        adobe_data_frame.to_csv(output_path("adobe_parsed_metrics.csv"), index=False)

    else:
        print("[PIPELINE ALERT] No Adobe-parsed data collected across any document.")

    log_complete("adobe_parsing.py")