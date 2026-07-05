"""
Shared configuration for the DSSA compliance pipeline.

Centralizes local file paths and canonical asset filenames so that
multi_tier_eval.py, adobe_parsing.py, and merge.py all reference the
SAME strings. Previously each script hardcoded its own copy of these
filenames — this is what let the Adobe/pypdf cross-validation check
in merge.py pass or fail silently based on whether two files typed a
name identically. Importing from one place makes that class of drift
structurally impossible instead of relying on discipline.
"""

import os



# Anchor to the project root regardless of the working directory a
# script is launched from (e.g. an IDE run config pointed at src/).
# pipeline_config.py lives in src/, so root is one level up.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Root directory for pipeline-generated output CSVs. Anchored to the
# project root (like AXE_CORE_PATH) so every script writes to the same
# place regardless of its own working directory.
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

# Root directory for local input assets (source PDFs + exported Adobe
# Acrobat DOCX reports). Defaults to a "data" folder under the project
# root so the pipeline runs the same way on any machine. Override
# per-environment with the DSSA_DATA_DIR variable instead of editing
# source files — e.g. on Windows:
# set DSSA_DATA_DIR=C:\Users\crook\PROJECTS\WCAG_compliance\data
DATA_DIR = os.environ.get("DSSA_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))

# axe-core is installed via `npm install axe-core --save-dev`, which places
# the minified bundle at node_modules/axe-core/axe.min.js under the
# project root.
AXE_CORE_PATH = os.path.join(PROJECT_ROOT, "node_modules", "axe-core", "axe.min.js")

# Canonical source-document filenames (used as Municipal_Code values
# across the pipeline, and as the join key for cross-validation).
NJLM_STATE_MAGAZINE_PDF = "February 2026 NJ Municipalities Magazine sample (PDF).pdf"
FEDERAL_GPO_REGISTER_PDF = "FR-2026-01-02.pdf"
PASSPORT_FORM_PDF = "ds11_pdf.pdf"

# Adobe Acrobat DOCX report exports (one per source PDF above).
NJLM_STATE_MAGAZINE_DOCX = "NJLMAccessibility Report.docx"
FEDERAL_GPO_REGISTER_DOCX = "FR2026Accessibility Report.docx"
PASSPORT_FORM_DOCX = "passport report.docx"


def asset_path(filename: str, data_dir: str = DATA_DIR) -> str:
    """Builds a full local path for a data asset under the configured data dir."""
    return os.path.join(data_dir, filename)

def log_start(script_name: str) -> None:
    """Prints a consistent run-start marker. Call at the top of __main__."""
    print(f"[RUNNING] {script_name}")

def log_complete(script_name: str) -> None:
    """Prints a consistent run-complete marker. Call at the end of __main__,
    ideally inside a `finally` block so it prints even after a caught error.
    """
    print(f"[COMPLETE] {script_name} finished running.")


def output_path(filename: str) -> str:
    """Builds a full path for a pipeline output file under OUTPUT_DIR,
    creating the directory if it doesn't exist yet."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, filename)