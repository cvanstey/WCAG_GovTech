"""
Multi-Tier Public Infrastructure Document and Anchor Parser.

Extends the core DSSA data pipeline under Zen of Python rules:
- Simple is better than complex: Separates web DOM audits from binary parsing.
- Special cases aren't special enough to break the rules: Both PDFs and URLs
  are converted into identical structured Pandas observations for the final paper.
"""

import os
from typing import Dict, List
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader  # Clean open-source PDF structural metadata parser

from pipeline_config import (asset_path, output_path,
    NJLM_STATE_MAGAZINE_PDF, FEDERAL_GPO_REGISTER_PDF, PASSPORT_FORM_PDF,
    log_start, log_complete,
)

# --- NAMESPACE SETTINGS ---
PDF_SEVERITY_WEIGHTS = {"Missing_Tags": 10, "Missing_Language": 5, "Missing_Title": 5}


def audit_directory_links(vendor_name: str, target_url: str) -> pd.DataFrame:
    """Parses informational directory lists for semantic link text violations.

    Explicit is better than implicit. This handles WCAG 2.2 SC 2.4.4 (Link Purpose).
    It catches ambiguous, non-descriptive anchor elements like 'Click Here' or 'View'.
    """
    try:
        request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(target_url, timeout=10, headers=request_headers)
        if response.status_code != 200:
            print(
                f"[HTTP WARNING] Non-200 response ({response.status_code}) "
                f"from {target_url} — link audit skipped, NOT a zero-violation result."
            )
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, "html.parser")
        records: List[Dict] = []
        anchor_elements = soup.find_all("a")

        for link in anchor_elements:
            link_text = str(link.text).strip().lower()
            if link_text in ["click here", "read more", "view", "pdf", "download"]:
                records.append({
                    "DSSA_Timestamp": pd.Timestamp.now(),
                    "GovTech_Vendor": vendor_name,
                    "Municipal_Code": "Directory_Hub",
                    "WCAG_Success_Criterion": "2.4.4",
                    "WCAG_Title": "Link Purpose (In Context)",
                    "Severity_Impact": "serious",
                    "Defect_Node_Count": 1,
                    "Litigation_Risk_Weight": 5
                })

        return pd.DataFrame(records)
    except Exception as error_trace:
        print(f"[ERROR] Link extraction bottleneck at {target_url}: {error_trace}")
        return pd.DataFrame()


def audit_binary_pdf_structure(vendor_name: str, file_path: str) -> pd.DataFrame:
    """Inspects underlying structural dictionaries inside a compiled PDF file.

    Errors should never pass silently. This inspects the Document Catalog roots
    for Section 508 and WCAG compliance keys (/MarkInfo, /Lang, and /Title).
    """
    if not os.path.exists(file_path):
        print(f"[FILE ALERT] Targeted PDF binary missing from local path: {file_path}")
        return pd.DataFrame()

    records: List[Dict] = []

    try:
        reader = PdfReader(file_path)
        root_catalog = reader.trailer["/Root"]

        is_tagged = False
        if "/MarkInfo" in root_catalog:
            is_tagged = root_catalog["/MarkInfo"].get("/Marked", False)

        if not is_tagged:
            records.append({
                "DSSA_Timestamp": pd.Timestamp.now(),
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "WCAG_Success_Criterion": "1.3.1",
                "WCAG_Title": "Info and Relationships",
                "Severity_Impact": "critical",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Tags"]
            })

        if "/Lang" not in root_catalog:
            records.append({
                "DSSA_Timestamp": pd.Timestamp.now(),
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "WCAG_Success_Criterion": "3.1.1",
                "WCAG_Title": "Language of Page",
                "Severity_Impact": "serious",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Language"]
            })

        document_info = reader.metadata
        if not document_info or not document_info.title:
            records.append({
                "DSSA_Timestamp": pd.Timestamp.now(),
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "WCAG_Success_Criterion": "2.4.2",
                "WCAG_Title": "Page Titled",
                "Severity_Impact": "serious",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Title"]
            })

        return pd.DataFrame(records)
    except Exception as pdf_error:
        print(f"[FATAL PDF CHECK] Structural check failed for {file_path}: {pdf_error}")
        return pd.DataFrame()


# --- INTEGRATED PROCESSING PIPELINE ---
if __name__ == "__main__":
    log_start("multi_tier_eval.py")
    print("[PIPELINE EXTENSION] Executing supplementary asset checks...")

    njlm_resources_url = "https://njlm.org"
    link_data_frame = audit_directory_links("NJLM_CivicPlus_CMS", njlm_resources_url)

    pdf_targets = {
        "NJLM_State_Magazine": asset_path(NJLM_STATE_MAGAZINE_PDF),
        "Federal_GPO_Register": asset_path(FEDERAL_GPO_REGISTER_PDF),
        "US_Passport": asset_path(PASSPORT_FORM_PDF)
    }

    pdf_data_frames: List[pd.DataFrame] = []
    for asset_name, local_file in pdf_targets.items():
        pdf_matrix = audit_binary_pdf_structure(asset_name, local_file)
        pdf_data_frames.append(pdf_matrix)

    all_data = [link_data_frame] + pdf_data_frames
    valid_frames = [df for df in all_data if not df.empty]

    if not valid_frames:
        print("\nNo accessibility findings were generated.")
        log_complete("multi_tier_eval.py")
        raise SystemExit(0)

    final_extended_matrix = pd.concat(valid_frames, ignore_index=True)

    print("\n[EXTENDED DATASET GENERATED]")
    print(
        final_extended_matrix.groupby(
            ["GovTech_Vendor", "WCAG_Success_Criterion"]
        )["Litigation_Risk_Weight"].sum()
    )

    final_extended_matrix.to_csv(
        output_path("extended_document_compliance_matrix.csv"),
        index=False
    )

    log_complete("multi_tier_eval.py")