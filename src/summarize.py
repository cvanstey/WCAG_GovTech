# summarize.py
"""
Human-readable console summary of a lighthouse.py scan run.

FIX: previously hardcoded "src/lighthouse_results_crawled.json" -- a
filename lighthouse.py's default --out (lighthouse_results.json) never
actually produces, and a bare relative path with the same cwd-dependent
drift risk merge.py/matrix.py used to have before those were anchored to
pipeline_config.OUTPUT_DIR. This only ever worked if you remembered to
type --out lighthouse_results_crawled.json by hand when *running*
lighthouse.py, with no error if you forgot -- it would just silently read
a stale file from a previous run, or crash with a bare FileNotFoundError
with no hint why.

Now: defaults to pipeline_config.output_path("lighthouse_results.json"),
the SAME default lighthouse.py itself writes to, so the common case needs
zero flags on either script. An explicit --in override is still available
for deliberately summarizing a differently-named run (e.g. if you renamed
one on purpose to keep a comparison).
"""

import argparse
import json
import os
import sys

from pipeline_config import output_path

DEFAULT_LIGHTHOUSE_JSON = output_path("lighthouse_results.json")


def load_results(json_path: str) -> list:
    if not os.path.exists(json_path):
        print(
            f"[FILE ALERT] Lighthouse results JSON missing from local path: {json_path}\n"
            f"Run lighthouse.py first (it writes here by default), or pass "
            f"--in <path> if you're summarizing a differently-named run.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_summary(results: list) -> None:
    print(f"{'Municipality':<20} {'Platform':<15} {'A11y':<6} {'BP':<6} {'Failed':<7} URL")
    print("-" * 100)
    for r in results:
        a11y = r.get("accessibility_score")
        bp = r.get("best_practices_score")
        failed = r.get("num_accessibility_audits_failed")
        if r.get("error"):
            print(f"{r['municipality']:<20} {r['platform']:<15} ERROR: {r['error'][:60]}")
            continue
        print(f"{r['municipality']:<20} {r['platform']:<15} {a11y!s:<6} {bp!s:<6} {failed!s:<7} {r['url']}")

    print("\n" + "=" * 100)
    print("FAILED AUDITS DETAIL")
    print("=" * 100)
    for r in results:
        if r.get("error") or not r.get("critical_a11y_issues"):
            continue
        print(f"\n{r['municipality']} — {r['url']}")
        for issue in r["critical_a11y_issues"]:
            wcag = issue.get("wcag_sc", "?")
            name = issue.get("wcag_name", "")
            print(f"  [{wcag}] {name or '(unmapped)'} — {issue['id']}: {issue['title']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Console summary of a lighthouse.py scan run."
    )
    parser.add_argument(
        "--in", dest="json_path", default=DEFAULT_LIGHTHOUSE_JSON,
        help="Path to lighthouse.py's --out JSON file "
             "(default: matches lighthouse.py's own default output location)",
    )
    args = parser.parse_args()

    results = load_results(args.json_path)
    print_summary(results)