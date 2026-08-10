"""
pdf_audit.py

Standalone PDF structural accessibility checker. Can audit a single PDF
(local file or URL) or every PDF discovered by the site crawler.

Usage:
    # Single file or URL
    python pdf_audit.py --file path/to/doc.pdf
    python pdf_audit.py --url https://example.com/doc.pdf

    # Every PDF found in the crawl log
    python pdf_audit.py --all --crawl-log src/crawled_targets.yaml
"""

import argparse
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd
import requests
import yaml
from pypdf import PdfReader

from pipeline_config import asset_path, output_path

PDF_SEVERITY_WEIGHTS = {"Missing_Tags": 10, "Missing_Language": 5, "Missing_Title": 5}
PDF_SKIP_REASONS = {"non_html", "http_200_or_non_html_content_type"}
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


def download_pdf(url: str, dest_dir: str) -> str:
    """Downloads a remote PDF into a local cache so pypdf can open it.
    Skips re-downloading if already cached."""
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(urlparse(url).path) or "downloaded.pdf"
    local_path = os.path.join(dest_dir, filename)

    if os.path.exists(local_path):
        return local_path

    response = requests.get(url, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(response.content)

    return local_path


def audit_binary_pdf_structure(vendor_name: str, file_path: str, source_url: Optional[str] = None) -> pd.DataFrame:
    """Inspects a PDF's Document Catalog for /MarkInfo, /Lang, and /Title —
    the WCAG 1.3.1 / 3.1.1 / 2.4.2 structural signals pypdf can check
    without a full PDF/UA validator."""
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
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "Source_URL": source_url,
                "WCAG_Success_Criterion": "1.3.1",
                "WCAG_Title": "Info and Relationships",
                "Severity_Impact": "critical",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Tags"],
            })

        if "/Lang" not in root_catalog:
            records.append({
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "Source_URL": source_url,
                "WCAG_Success_Criterion": "3.1.1",
                "WCAG_Title": "Language of Page",
                "Severity_Impact": "serious",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Language"],
            })

        document_info = reader.metadata
        if not document_info or not document_info.title:
            records.append({
                "GovTech_Vendor": vendor_name,
                "Municipal_Code": os.path.basename(file_path),
                "Source_URL": source_url,
                "WCAG_Success_Criterion": "2.4.2",
                "WCAG_Title": "Page Titled",
                "Severity_Impact": "serious",
                "Defect_Node_Count": 1,
                "Litigation_Risk_Weight": PDF_SEVERITY_WEIGHTS["Missing_Title"],
            })

        return pd.DataFrame(records)

    except Exception as pdf_error:
        print(f"[FATAL PDF CHECK] Structural check failed for {file_path}: {pdf_error}")
        return pd.DataFrame()


def audit_one(source: str, vendor_name: Optional[str] = None, cache_dir: Optional[str] = None) -> pd.DataFrame:
    """Audits a single PDF, whether given as a local path or a URL."""
    cache_dir = cache_dir or output_path("pdf_cache")

    if is_url(source):
        try:
            local_file = download_pdf(source, cache_dir)
        except Exception as download_error:
            print(f"[DOWNLOAD FAILED] {source}: {download_error}")
            return pd.DataFrame()
        vendor_name = vendor_name or urlparse(source).netloc
        return audit_binary_pdf_structure(vendor_name, local_file, source_url=source)

    vendor_name = vendor_name or os.path.basename(source)
    return audit_binary_pdf_structure(vendor_name, source, source_url=None)


def discover_crawled_pdfs(crawl_log_path: str) -> List[Dict]:
    """Reads crawled_targets.yaml's crawl_log and returns every entry that
    was skipped specifically because it pointed at a PDF.

    Two skip reasons need different filtering:
      - "http_200_or_non_html_content_type": the crawler already fetched
        the page and its Content-Type header confirmed non-HTML — this is
        verified, so no extension check is needed (catches URLs like the
        NJLM OPRA form that don't literally end in .pdf).
      - "non_html": skipped by extension alone, before any request was
        made — .pdf is required here since that's the only signal we have.
    """
    with open(crawl_log_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    pdf_entries = []
    for entry in config.get("crawl_log", []):
        reason = entry.get("skipped_reason")
        url_lower = entry["url"].lower()

        if reason == "non_html" and url_lower.endswith(".pdf"):
            pdf_entries.append({
                "vendor": entry["platform"],
                "municipality": entry["municipality"],
                "url": entry["url"],
            })
        elif reason and reason.startswith("http_200_or_non_html_content_type"):
            pdf_entries.append({
                "vendor": entry["platform"],
                "municipality": entry["municipality"],
                "url": entry["url"],
            })

    return pdf_entries


def audit_all_crawled(crawl_log_path: str, cache_dir: Optional[str] = None) -> pd.DataFrame:
    """Audits every PDF the crawler discovered."""
    cache_dir = cache_dir or output_path("pdf_cache")
    entries = discover_crawled_pdfs(crawl_log_path)
    print(f"[PDF DISCOVERY] Found {len(entries)} crawled PDF(s) to audit.")

    frames = []
    for entry in entries:
        print(f"  Auditing ({entry['vendor']}) -> {entry['url']}")
        frame = audit_one(entry["url"], vendor_name=entry["vendor"], cache_dir=cache_dir)
        if not frame.empty:
            frames.append(frame)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Audit PDF(s) for basic WCAG structural signals.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a local PDF")
    group.add_argument("--url", help="URL of a remote PDF")
    group.add_argument("--all", action="store_true", help="Audit every PDF found in the crawl log")
    parser.add_argument("--crawl-log", default=asset_path("crawled_targets.yaml"))
    parser.add_argument("--vendor", help="Override the GovTech_Vendor label for --file/--url")
    parser.add_argument("--out", default=output_path("pdf_audit_results.csv"))
    args = parser.parse_args()

    if args.all:
        result = audit_all_crawled(args.crawl_log)
    else:
        source = args.file or args.url
        result = audit_one(source, vendor_name=args.vendor)

    if result.empty:
        print("\nNo accessibility findings (or all audited PDFs passed the structural checks).")
    else:
        print(f"\n[FOUND {len(result)} ISSUE(S)]")
        print(result[["GovTech_Vendor", "Municipal_Code", "WCAG_Success_Criterion", "Severity_Impact"]])
        result.to_csv(args.out, index=False)
        print(f"\nWrote results to {args.out}")


if __name__ == "__main__":
    main()