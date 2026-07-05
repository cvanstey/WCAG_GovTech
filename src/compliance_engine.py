"""
NJ Public Digital Infrastructure Audit Data Pipeline.

Built on Downey's criteria of incremental data discretization and PEP 20 guidelines.
- Explicit is better than implicit: All functions explicitly type out payloads.
- Flat is better than nested: Avoids deeply structured loop architecture.
- Errors should never pass silently: Implements distinct try/except telemetry blocks.
"""

import os
from typing import Dict, List, Optional
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from pipeline_config import AXE_CORE_PATH, output_path, log_start, log_complete



# --- THE NAMESPACE (Namespaces are one honking great idea!) ---

DEFAULT_TIMEOUT = 30  # Seconds to wait for script injection
SEVERITY_WEIGHTS = {"critical": 10, "serious": 5, "moderate": 2, "minor": 1}

# axe-core is installed via `npm install axe-core --save-dev`, which places
# the minified bundle at node_modules/axe-core/axe.min.js


# Explicit municipal labeling. Replaces fragile URL-param/fragment parsing,
# since SPA routes (e.g. Tyler's #/home) and bare landing pages carry no
# parseable ID at all.
MUNICIPAL_LABELS = {
    "Cite_E_net": "Plainfield_NJ",
    "HLS_Systems_PropertyTaxInquiry": "JerseyCity_NJ",
    "Edmunds_WIPP": "Multi_Tenant_Generic",
    "Tyler_Tech_EnerGov": "JerseyCity_NJ",
}


def build_driver() -> webdriver.Chrome:
    """Configures and initializes a headless Chrome WebDriver instance.

    Explicit is better than implicit. Standard headless configuration for
    running an accessibility scan against public-facing pages.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Sparse is better than dense
    chrome_options.add_argument("--disable-gpu")
    chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def load_axe_core_library(file_path: str = AXE_CORE_PATH) -> str:
    """Reads the local axe-core source file into memory for page injection.

    Errors should never pass silently. If the required local open-source file
    is missing, the execution explicitly surfaces a clear FileNotFoundError.
    """
    if not os.path.exists(file_path):
        msg = (
            f"Axe-core source framework missing at: {file_path}. "
            "Run `npm install axe-core --save-dev` from the project root."
        )
        raise FileNotFoundError(msg)

    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


MIN_RENDERED_TEXT_LENGTH = 200  # tune based on what "loaded" looks like for these portals


def wait_for_spa_render(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """Blocks until the page appears to have finished client-side rendering.

    Errors should never pass silently. Rather than guessing with a fixed sleep,
    this polls the DOM until either a real content threshold is met or we
    explicitly time out and log that fact.
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_element(By.TAG_NAME, "body").text.strip()) > MIN_RENDERED_TEXT_LENGTH
        )
        return True
    except Exception:
        print(f"[RENDER TIMEOUT] Page did not reach content threshold within {timeout}s: {driver.current_url}")
        return False


def execute_compliance_scan(driver: webdriver.Chrome, url: str, axe_script: str) -> Optional[Dict]:
    try:
        driver.get(url)

        rendered_ok = wait_for_spa_render(driver)
        if not rendered_ok:
            print(f"[METRIC WARNING] Proceeding with scan despite possible incomplete render: {url}")
            page_length = len(driver.page_source)
            body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
            print(f"[DEBUG] page_source length: {page_length} chars")
            print(f"[DEBUG] visible body text: {body_text[:300]!r}")
            print(f"[DEBUG] current URL after load: {driver.current_url}")

        driver.execute_script(axe_script)
        raw_results = driver.execute_async_script(
            "var callback = arguments[arguments.length - 1];"
            "axe.run({runOnly: {type: 'tag', values: ['wcag2a', 'wcag21aa']}}, function(err, results) {"
            "    if (err) throw err;"
            "    callback(results);"
            "});"
        )
        return raw_results
    except Exception as error_context:
        print(f"[METRIC FAILURE] System connection error targeting {url}: {error_context}")
        return None


def transform_violations_to_dataframe(vendor_name: str, town_id: str, scan_payload: Optional[Dict]) -> pd.DataFrame:
    """Parses raw JSON scan parameters into a clean, flat statistical DataFrame.

    Flat is better than nested. This function unwraps complex JSON objects
    and formats them immediately into structured observations for analysis.
    """
    if not scan_payload or "violations" not in scan_payload:
        return pd.DataFrame()

    records_list: List[Dict] = []
    violations_array = scan_payload["violations"]

    for issue in violations_array:
        rule_id = issue.get("id", "unknown-rule")
        impact_severity = issue.get("impact", "moderate")
        nodes_affected = len(issue.get("nodes", []))

        severity_multiplier = SEVERITY_WEIGHTS.get(impact_severity, 2)
        calculated_risk_score = nodes_affected * severity_multiplier

        records_list.append({
            "DSSA_Timestamp": pd.Timestamp.now(),
            "GovTech_Vendor": vendor_name,
            "Municipal_Code": town_id,
            "WCAG_Success_Criterion": rule_id,
            "Severity_Impact": impact_severity,
            "Defect_Node_Count": nodes_affected,
            "Litigation_Risk_Weight": calculated_risk_score
        })

    return pd.DataFrame(records_list)


# --- THE EXECUTION PIPELINE (Now is better than never) ---
if __name__ == "__main__":
    log_start("compliance_engine.py")
    target_endpoints = {
        "Cite_E_net": "https://www.cit-e.net/plainfield-nj/cn/TaxBill_Std/",
        "HLS_Systems_PropertyTaxInquiry": "https://apps.hlssystems.com/JerseyCity/PropertyTaxInquiry",
        "Edmunds_WIPP": "https://wipp.edmundsassoc.com/Wipp/?wippid=0409",
        "Tyler_Tech_EnerGov": "https://jerseycitynj-energovpub.tylerhost.net/apps/selfservice#/home",

    }

    print("[PIPELINE INITIALIZATION] Initializing multi-tier compliance script...")

    try:
        web_driver = build_driver()
        axe_core_source = load_axe_core_library()
        aggregated_datasets: List[pd.DataFrame] = []

        for vendor, target_url in target_endpoints.items():
            print(f"[AUDITING DATASET] Fetching public interface layers for: {vendor}")

            raw_scan_output = execute_compliance_scan(web_driver, target_url, axe_core_source)

            # Explicit municipal label lookup — fully replaces URL-based parsing
            town_label = MUNICIPAL_LABELS.get(vendor, "Unlabeled_NJ_Entity")

            flat_dataframe = transform_violations_to_dataframe(vendor, town_label, raw_scan_output)
            aggregated_datasets.append(flat_dataframe)

        if aggregated_datasets:
            master_dssa_matrix = pd.concat(aggregated_datasets, ignore_index=True)
            # FIX: was writing to a bare relative "nj_govtech_compliance_
            # matrix.csv" (wherever cwd happened to be). Routed through
            # output_path() to match where merge.py now looks for it
            # (pipeline_config.OUTPUT_DIR), the same fix applied to
            # adobe_parsing.py's and multi_tier_eval.py's outputs.
            master_dssa_matrix.to_csv(output_path("nj_govtech_compliance_matrix.csv"), index=False)
            print("\n[PIPELINE SUCCESS] Master compliance database generated successfully.")
            print(master_dssa_matrix.groupby(["GovTech_Vendor", "Severity_Impact"])["Defect_Node_Count"].sum())
        else:
            print("[PIPELINE ALERT] No valid data entries were retrieved.")

    except FileNotFoundError as fnf_error:
        print(f"\n[CRITICAL BUILD ERROR] Pipeline stopped: {fnf_error}")
    except Exception as global_fatal_error:
        print(f"\n[FATAL SYSTEM EXCEPTION] Unhandled error trace: {global_fatal_error}")
    finally:
        # FIX: this block previously contained a second, dead copy of the
        # entire __main__ try/except/finally structure (with an empty `...`
        # body) nested inside this one. It never did anything except call
        # web_driver.quit() a second time and — worse — it meant
        # log_complete() only ran when web_driver had been created, so a
        # FileNotFoundError from load_axe_core_library() (raised before
        # web_driver exists) would skip the completion marker entirely.
        # log_complete() now always runs, matching every other script's
        # pattern of logging completion in a `finally` regardless of outcome.
        if 'web_driver' in locals():
            web_driver.quit()
        log_complete("compliance_engine.py")