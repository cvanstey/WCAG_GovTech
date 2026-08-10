"""
lighthouse_scan.py

Runs Google Lighthouse (via CLI subprocess) against a list of municipal
govtech target URLs and normalizes results into a row schema compatible
with the axe-core / PDF-checker merge step.

Requirements:
    - Node.js + `npm install -g lighthouse` (or `npx lighthouse` per-call)
    - Chrome/Chromium available on PATH or via CHROME_PATH env var

Usage:
    python lighthouse_scan.py --targets targets.yaml --out lighthouse_results.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import yaml

import platform

# --- Add near the top, after imports ---

# Maps common Lighthouse/axe accessibility audit IDs to their WCAG 2.1 success criterion.
# Not exhaustive -- Lighthouse ships ~30-40 a11y audits; extend as new IDs appear in your data.
WCAG_MAPPING = {
    "color-contrast": ("1.4.3", "Contrast (Minimum)", "AA"),
    "image-alt": ("1.1.1", "Non-text Content", "A"),
    "input-image-alt": ("1.1.1", "Non-text Content", "A"),
    "object-alt": ("1.1.1", "Non-text Content", "A"),
    "video-caption": ("1.2.2", "Captions (Prerecorded)", "A"),
    "audio-caption": ("1.2.1", "Audio-only and Video-only (Prerecorded)", "A"),
    "html-has-lang": ("3.1.1", "Language of Page", "A"),
    "html-lang-valid": ("3.1.1", "Language of Page", "A"),
    "document-title": ("2.4.2", "Page Titled", "A"),
    "link-name": ("2.4.4", "Link Purpose (In Context)", "A"),
    "button-name": ("4.1.2", "Name, Role, Value", "A"),
    "label": ("1.3.1", "Info and Relationships", "A"),
    "form-field-multiple-labels": ("1.3.1", "Info and Relationships", "A"),
    "aria-allowed-attr": ("4.1.2", "Name, Role, Value", "A"),
    "aria-required-attr": ("4.1.2", "Name, Role, Value", "A"),
    "aria-required-children": ("1.3.1", "Info and Relationships", "A"),
    "aria-required-parent": ("1.3.1", "Info and Relationships", "A"),
    "aria-roles": ("4.1.2", "Name, Role, Value", "A"),
    "aria-valid-attr": ("4.1.2", "Name, Role, Value", "A"),
    "aria-valid-attr-value": ("4.1.2", "Name, Role, Value", "A"),
    "aria-hidden-focus": ("4.1.2", "Name, Role, Value", "A"),
    "duplicate-id-active": ("4.1.1", "Parsing", "A"),
    "duplicate-id-aria": ("4.1.1", "Parsing", "A"),
    "focus-traps": ("2.1.2", "No Keyboard Trap", "A"),
    "focusable-controls": ("2.1.1", "Keyboard", "A"),
    "heading-order": ("1.3.1", "Info and Relationships", "A"),
    "landmark-one-main": ("1.3.1", "Info and Relationships", "A"),
    "list": ("1.3.1", "Info and Relationships", "A"),
    "listitem": ("1.3.1", "Info and Relationships", "A"),
    "meta-viewport": ("1.4.4", "Resize Text", "AA"),
    "tabindex": ("2.4.3", "Focus Order", "A"),
    "target-size": ("2.5.8", "Target Size (Minimum)", "AA"),
    "select-name": ("4.1.2", "Name, Role, Value", "A"),
    "table-fake-caption": ("1.3.1", "Info and Relationships", "A"),
    "td-headers-attr": ("1.3.1", "Info and Relationships", "A"),
    "th-has-data-cells": ("1.3.1", "Info and Relationships", "A"),
    "valid-lang": ("3.1.2", "Language of Parts", "AA"),
}


def wcag_lookup(audit_id: str) -> dict:
    """Returns WCAG SC info for a Lighthouse audit id, or an 'unmapped' placeholder."""
    sc, name, level = WCAG_MAPPING.get(audit_id, (None, None, None))
    if sc is None:
        return {"sc": "Unmapped", "sc_name": "(not in local mapping table)", "level": "?"}
    return {"sc": sc, "sc_name": name, "level": level}

@dataclass
class LighthouseResult:
    municipality: str
    url: str
    platform: str            # e.g. "EnerGov", "Edmunds WIPP", "NJLM"
    accessibility_score: Optional[float]
    best_practices_score: Optional[float]
    performance_score: Optional[float]
    seo_score: Optional[float]
    num_accessibility_audits_failed: Optional[int]
    critical_a11y_issues: list       # list of {id, title, description}
    scan_timestamp: float
    error: Optional[str] = None


def run_lighthouse(url: str, timeout_sec: int = 90) -> dict:
    """
    Invokes the Lighthouse CLI headlessly and returns parsed JSON output.
    Raises subprocess.CalledProcessError or json.JSONDecodeError on failure.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = tmp.name

    cmd = [
        "npx", "lighthouse", url,
        "--output=json",
        f"--output-path={out_path}",
        "--only-categories=accessibility,best-practices,performance,seo",
        "--chrome-flags=--headless --no-sandbox --disable-gpu",
        # EnerGov/Angular SPAs are slow to bootstrap -- give them room
        "--max-wait-for-load=45000",
        "--throttling-method=simulate",
        "--quiet",
    ]

    subprocess.run(
        cmd,
        check=True,
        timeout=timeout_sec,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        shell=(platform.system() == "Windows"),
    )

    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    Path(out_path).unlink(missing_ok=True)
    return data


def extract_result(municipality: str, url: str, platform: str, raw: dict) -> LighthouseResult:
    categories = raw.get("categories", {})
    audits = raw.get("audits", {})

    def score(cat_key: str) -> Optional[float]:
        cat = categories.get(cat_key)
        if cat and cat.get("score") is not None:
            return round(cat["score"] * 100, 1)
        return None

    a11y_audit_refs = categories.get("accessibility", {}).get("auditRefs", [])
    failed = []
    for ref in a11y_audit_refs:
        audit = audits.get(ref["id"], {})
        if audit.get("score") is not None and audit["score"] < 1:
            wcag = wcag_lookup(ref["id"])
            failed.append({
                "id": ref["id"],
                "title": audit.get("title", ""),
                "description": audit.get("description", ""),
                "wcag_sc": wcag["sc"],
                "wcag_name": wcag["sc_name"],
                "wcag_level": wcag["level"],
            })

    return LighthouseResult(
        municipality=municipality,
        url=url,
        platform=platform,
        accessibility_score=score("accessibility"),
        best_practices_score=score("best-practices"),
        performance_score=score("performance"),
        seo_score=score("seo"),
        num_accessibility_audits_failed=len(failed),
        critical_a11y_issues=failed,
        scan_timestamp=time.time(),
    )


def scan_target(municipality: str, url: str, platform: str, retries: int = 1) -> LighthouseResult:
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw = run_lighthouse(url)
            return extract_result(municipality, url, platform, raw)
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout: {e}"
        except subprocess.CalledProcessError as e:
            last_err = f"lighthouse cli error: {e.stderr.decode(errors='ignore')[:500]}"
        except (json.JSONDecodeError, FileNotFoundError) as e:
            last_err = f"parse error: {e}"
        time.sleep(2)

    return LighthouseResult(
        municipality=municipality,
        url=url,
        platform=platform,
        accessibility_score=None,
        best_practices_score=None,
        performance_score=None,
        seo_score=None,
        num_accessibility_audits_failed=None,
        critical_a11y_issues=[],
        scan_timestamp=time.time(),
        error=last_err,
    )

def load_targets(path: str) -> list:
    """
    Expects a YAML file like:

    targets:
      - municipality: "Jersey City"
        platform: "EnerGov"
        url: "https://jerseycitynj-energovpub.tylerhost.net/apps/selfservice/JerseyCityNJProd"
      - municipality: "Example Township"
        platform: "Edmunds WIPP"
        url: "https://wipp.edmundsgovtech.cloud/..."
    """
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["targets"]

def print_report(results: list, file=sys.stderr):
    print("\n" + "=" * 70, file=file)
    print("ACCESSIBILITY REPORT — WCAG-mapped failed audits", file=file)
    print("=" * 70, file=file)
    for r in results:
        print(f"\n{r['municipality']} ({r['platform']}) — score: {r['accessibility_score']}", file=file)
        print(f"  {r['url']}", file=file)
        if r.get("error"):
            print(f"  ERROR: {r['error']}", file=file)
            continue
        if not r["critical_a11y_issues"]:
            print("  No failed accessibility audits.", file=file)
            continue
        for issue in r["critical_a11y_issues"]:
            print(f"  - [{issue['wcag_sc']} {issue['wcag_level']}] {issue['wcag_name']}", file=file)
            print(f"      Lighthouse audit: {issue['id']} — {issue['title']}", file=file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", required=True, help="YAML file of scan targets")
    parser.add_argument("--out", default="lighthouse_results.json")
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()

    targets = load_targets(args.targets)
    results = []

    for i, t in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] Scanning {t['municipality']} ({t['platform']}) -> {t['url']}",
              file=sys.stderr)
        result = scan_target(t["municipality"], t["url"], t["platform"], retries=args.retries)
        results.append(asdict(result))
        if result.error:
            print(f"    WARNING: {result.error}", file=sys.stderr)
        else:
            print(f"    a11y={result.accessibility_score}  "
                  f"best_practices={result.best_practices_score}  "
                  f"failed_audits={result.num_accessibility_audits_failed}",
                  file=sys.stderr)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote {len(results)} results to {args.out}", file=sys.stderr)
    print_report(results)

if __name__ == "__main__":
    main()

    #python src\lighthouse.py --targets src\targets.yaml --out lighthouse_results.json