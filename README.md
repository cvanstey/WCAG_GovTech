# A Multi-Tier Technical Debt Audit of WCAG Compliance in New Jersey GovTech

An empirical, multi-tiered black-box accessibility audit of public-facing
digital infrastructure across municipal, state, and federal government
systems in New Jersey, built to accompany the research paper
*"A Multi-Tier Technical Debt Audit of WCAG Compliance in New Jersey GovTech"* (Stockton University, DSSA, Summer 2026).

## What this is

This project combines multiple independent evaluation channels into a unified research pipeline capable of producing cross-validated accessibility datasets suitable for empirical analysis.

1. Are New Jersey government digital platforms meeting WCAG 2.1 Level AA regardless of vendor or platform?
2. Given the ADA Title II compliance deadlines (April 2027 and April 2028), can we assess current accessibility gap?

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

## Pipeline

<pre>
Website Scan
     │
     ▼
Selenium + axe-core
     │
     ▼
Web Findings
     │
     │
PDF Scan ──► pypdf ───────────────┐
                                  │
Adobe Reports ─► Acrobat Parser ──┤
                                  ▼
                          merge.py
                                  ▼
                    Master Research Dataset
                                  ▼
                   Charts • Tables • Analysis
</pre>

The pipeline intentionally uses multiple independent evaluation methods rather than relying on a single accessibility engine.

## Methodology summary

Web Accessibility Evaluation

compliance_engine.py

Selenium-driven headless Chrome sessions
axe-core injected directly into the page DOM
Evaluation against:
WCAG 2.0 A
WCAG 2.1 AA
Structured defect extraction into a normalized research dataset
PDF Accessibility Evaluation

multi_tier_eval.py

Automated structural inspection using pypdf, including:

Document tag-tree detection
Language metadata
Document title metadata
Additional directory link analysis
Manual Cross-Validation

adobe_parsing.py

Parses exported Adobe Acrobat Pro accessibility reports to independently validate automated PDF findings.

This stage requires Adobe Acrobat Pro and cannot be fully automated.

Dataset Assembly

merge.py

Combines findings from all audit channels into a unified master dataset used for statistical analysis and visualization.

module.py

Reporting feature summarizing findings.

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
python src/module.py              # reporting and plot writer
```

Each script logs `[RUNNING]` / `[COMPLETE]` markers and writes its output
to `output/` via `pipeline_config.output_path()`, so results land in the
same place regardless of which directory a script is launched from.
src/
pipeline_config.py     # Shared paths, canonical filenames, logging helpers
compliance_engine.py   # Live web-interface axe-core scans
multi_tier_eval.py     # Automated pypdf structural checks (PDF tier)
adobe_parsing.py       # Adobe Acrobat DOCX report parser (PDF tier)
merge.py               # Cross-validation + master dataset assembly
data/                    # Source PDFs + Adobe DOCX exports (see note below)
output/                  # Generated CSVs (defect matrices, cross-validation results)
node_modules/axe-core/   # axe-core library (npm install axe-core --save-dev)

[Contact info / LinkedIn — (https://www.linkedin.com/in/cvanstey/)]
