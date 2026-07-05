# The Vendor Gap: WCAG Compliance Audit of NJ GovTech

An empirical, multi-tiered black-box accessibility audit of public-facing
digital infrastructure across municipal, state, and federal government
systems in New Jersey — built to accompany the research paper
*"The Vendor Gap: A Technical Debt Audit of WCAG Compliance in New Jersey
GovTech"* (Stockton University, DSSA, Summer 2026).

## What this is

This pipeline programmatically audits live government websites and
distributed government PDFs against WCAG 2.1 Level AA success criteria,
using a combination of automated tooling and manual cross-validation. It
was built to answer two questions:

1. Are New Jersey's government digital platforms — across vendors,
   municipalities, and levels of government — currently meeting WCAG 2.1
   AA, or is non-compliance widespread regardless of vendor?
2. Given the ADA Title II final rule's compliance deadlines (April 2027
   for larger entities, April 2028 for smaller ones), how large is the
   gap today?

The full findings, methodology discussion, and limitations are in the
paper (linked below). This repository contains the reproducible portion
of that methodology.

## Disclosure

The author is a former employee of Edmunds GovTech, one of the vendors
audited here. All findings regarding Edmunds' platform were obtained
using the same black-box methodology applied to every other target in
this study — public endpoints only, no internal access, no non-public
technical information. See the paper's Methodology chapter for the full
disclosure statement. Every vendor named in this study was contacted
prior to publication to confirm findings and offer the opportunity to
respond.

## Methodology summary

Two independent audit channels:

- **Live web-interface scanning** (`compliance_engine.py`) — a headless
  Chrome session (Selenium) with the [axe-core](https://github.com/dequelabs/axe-core)
  accessibility engine injected into the page DOM, scanning against
  `wcag2a` and `wcag21aa` rule sets.
- **PDF structural auditing** — a dual-channel check on distributed
  government PDFs:
  - `multi_tier_eval.py`: automated structural checks via `pypdf`
    (tag-tree presence, language declaration, title metadata).
  - `adobe_parsing.py`: parses Adobe Acrobat Pro's exported `.docx`
    accessibility reports for a full manual cross-validation pass.

The web-scan and `pypdf` components rely only on public endpoints and
open-source tooling and are fully reproducible by anyone. The Adobe
Acrobat cross-validation step requires a licensed copy of Acrobat Pro
and a manual export step, and is not independently automatable.



> **Note on `data/`:** This folder contains source documents used in the
> audit. The Federal Register document and DS-11 passport form are
> public federal records. If you're replicating this against your own
> jurisdiction's documents, point `DSSA_DATA_DIR` at your own data
> directory rather than relying on the contents here.

## Running the pipeline

Requirements: Python 3.x, Node.js (for axe-core), Chrome/Chromedriver,
Adobe Acrobat Pro (only required for the manual cross-validation step).

```bash
npm install axe-core --save-dev
pip install -r requirements.txt   # selenium, pandas, python-docx, pypdf

# Optional: point at a custom data directory
set DSSA_DATA_DIR=C:\path\to\your\data      # Windows
export DSSA_DATA_DIR=/path/to/your/data     # macOS/Linux

python src/compliance_engine.py   # live web-interface scan
python src/multi_tier_eval.py     # automated PDF structural check
python src/adobe_parsing.py       # parse Adobe Acrobat DOCX reports
python src/merge.py               # assemble cross-validated master dataset
```

Each script logs `[RUNNING]` / `[COMPLETE]` markers and writes its output
to `output/` via `pipeline_config.output_path()`, so results land in the
same place regardless of which directory a script is launched from.

## Auditing a new target

To scan an additional web-based system, add an entry to
`target_endpoints` in `compliance_engine.py`:

```python
target_endpoints = {
    "Your_Vendor_Name": "https://your-target-url.example.com/",
}
```

To audit an additional PDF, add its canonical filename as a constant in
`pipeline_config.py` (both the source PDF and its Adobe-exported `.docx`
report), following the existing `_PDF` / `_DOCX` naming pattern, then add
a corresponding entry to the `reports` dict in `adobe_parsing.py`.

## Findings summary

Full results are reported in the paper. In brief: every system audited —
across four municipal vendors, a state association, and two federal
agencies — showed at least one WCAG 2.1 AA structural defect. No vendor
or tier demonstrated full conformance. See the paper for severity
breakdowns, the automated-vs-manual detection gap, and this study's
stated limitations (small per-tier sample sizes; automated coverage
limited to structural/programmatic criteria; diagnostic, not causal,
design).

## Paper

Email cynthiaanstey@gmail.com for a copy. 

## Limitations

This is a research artifact, not a certified compliance audit. It does
not constitute a legal determination of ADA Title II or Section 508
conformance. Automated tooling in this pipeline detects only a subset of
WCAG success criteria (primarily structural/programmatic checks); visual
and human-judgment criteria (color contrast, keyboard-trap testing,
whether alt text is actually accurate) are outside this pipeline's
current scope. See the paper's Methodology and Limitations sections for
full detail.

## Contact

[Your contact info / LinkedIn - (https://www.linkedin.com/in/cvanstey/)]

## Repository structure
src/
pipeline_config.py     # Shared paths, canonical filenames, logging helpers
compliance_engine.py   # Live web-interface axe-core scans
multi_tier_eval.py     # Automated pypdf structural checks (PDF tier)
adobe_parsing.py       # Adobe Acrobat DOCX report parser (PDF tier)
merge.py               # Cross-validation + master dataset assembly
data/                    # Source PDFs + Adobe DOCX exports (see note below)
output/                  # Generated CSVs (defect matrices, cross-validation results)
node_modules/axe-core/   # axe-core library (npm install axe-core --save-dev)

> **Note on `data/`:** This folder contains source documents used in the
> audit. The Federal Register document and DS-11 passport form are
> public federal records. If you're replicating this against your own
> jurisdiction's documents, point `DSSA_DATA_DIR` at your own data
> directory rather than relying on the contents here.

## Running the pipeline

Requirements: Python 3.x, Node.js (for axe-core), Chrome/Chromedriver,
Adobe Acrobat Pro (only required for the manual cross-validation step).

```bash
npm install axe-core --save-dev
pip install -r requirements.txt   # selenium, pandas, python-docx, pypdf

# Optional: point at a custom data directory
set DSSA_DATA_DIR=C:\path\to\your\data      # Windows
export DSSA_DATA_DIR=/path/to/your/data     # macOS/Linux

python src/compliance_engine.py   # live web-interface scan
python src/multi_tier_eval.py     # automated PDF structural check
python src/adobe_parsing.py       # parse Adobe Acrobat DOCX reports
python src/merge.py               # assemble cross-validated master dataset
```

whether alt text is actually accurate) are outside this pipeline's
current scope. See the paper's Methodology and Limitations sections for
full detail.

## Contact

[Your contact info / LinkedIn — add here]
