"""
remediation_guide.py

Maps accessibility rule identifiers (both axe-core rule ids and raw WCAG
Success Criterion numbers, since master_appendix.csv currently contains
BOTH under the same WCAG_Success_Criterion column -- axe rule ids from
compliance_engine.py, numeric SCs from multi_tier_eval.py/adobe_parsing.py)
to plain-language explanations, who is positioned to fix each issue, and
concrete remediation steps.

Responsible_Party values:
    "Web Developer"    -- requires template/theme/code changes
    "Content Author"   -- fixable in the CMS by whoever posts pages/PDFs
    "GovTech Vendor"   -- requires the platform vendor (CivicPlus, Tyler,
                           Edmunds, etc.) to patch their underlying template
"""

from typing import Dict, Optional
import pandas as pd

REMEDIATION_GUIDE: Dict[str, dict] = {

    # ------------------------------------------------------------------
    # PDF structural checks (multi_tier_eval.py / pdf_audit.py output)
    # ------------------------------------------------------------------
    "1.3.1": {
        "title": "Info and Relationships (Tagged PDF)",
        "explanation": (
            "The PDF has no internal tag structure, so screen readers can't "
            "tell headings from body text, tables from paragraphs, or "
            "determine reading order."
        ),
        "responsible_party": "Content Author",
        "fix_steps": [
            "Re-export the source document (Word/InDesign) with 'tagged PDF' "
            "enabled, rather than printing/flattening to PDF.",
            "If only a scanned/flattened PDF exists, run it through Adobe "
            "Acrobat Pro's 'Autotag Document', then manually verify reading "
            "order and table structure.",
        ],
    },
    "3.1.1": {
        "title": "Language of Page",
        "explanation": (
            "The PDF's document properties don't declare a language, so "
            "screen readers may mispronounce the text using the wrong "
            "language's pronunciation rules."
        ),
        "responsible_party": "Content Author",
        "fix_steps": [
            "In Acrobat Pro: File > Properties > Advanced > Reading Options "
            "> Language, set to English (US).",
            "In Word before export: Review > Language > Set Proofing "
            "Language, then re-save as PDF.",
        ],
    },
    "2.4.2": {
        "title": "Page Titled",
        "explanation": (
            "The PDF has no document title in its metadata, so it shows up "
            "in browser tabs and screen readers as a raw filename instead "
            "of a descriptive title."
        ),
        "responsible_party": "Content Author",
        "fix_steps": [
            "In Acrobat Pro: File > Properties > Description > Title, enter "
            "a descriptive title (not the filename).",
            "In Word: File > Info > Properties > Title, set before "
            "exporting to PDF.",
        ],
    },

    # ------------------------------------------------------------------
    # axe-core / Lighthouse rule ids (compliance_engine.py output)
    # ------------------------------------------------------------------
    "link-name": {
        "title": "Link Purpose (In Context)",
        "explanation": (
            "A link has no accessible text -- often an icon-only link or "
            "an image link with no alt text -- so screen reader users hear "
            "'link' with no indication of where it goes."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Add visible or screen-reader-only text inside the <a> tag "
            "(e.g. <span class=\"sr-only\">View agenda</span>).",
            "If the link wraps an <img>, ensure the image has a "
            "descriptive alt attribute.",
        ],
    },
    "heading-order": {
        "title": "Info and Relationships (Heading Order)",
        "explanation": (
            "Heading levels skip (e.g. H2 straight to H4) instead of "
            "descending in order, which breaks the page outline screen "
            "reader users rely on to navigate."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Audit the page's heading hierarchy and renumber so each "
            "level only steps down by one (H1 -> H2 -> H3).",
            "If a heading is styled a certain size purely for visual "
            "reasons, change the CSS, not the heading level.",
        ],
    },
    "color-contrast": {
        "title": "Contrast (Minimum)",
        "explanation": (
            "Text color doesn't contrast enough against its background "
            "to meet the 4.5:1 minimum ratio, making it hard to read for "
            "low-vision users."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Run the flagged color pairs through a contrast checker "
            "(e.g. WebAIM Contrast Checker) and darken/lighten until "
            "they clear 4.5:1 (3:1 for large text).",
            "Update the site's design tokens/theme so the fix applies "
            "sitewide, not just on one page.",
        ],
    },
    "aria-hidden-focus": {
        "title": "Name, Role, Value (aria-hidden focus trap)",
        "explanation": (
            "An element marked aria-hidden=\"true\" still contains a "
            "focusable control (like a button or link), so keyboard users "
            "can tab into content that's invisible to screen readers."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Either remove aria-hidden from the container, or add "
            "tabindex=\"-1\" to every focusable child inside it.",
            "This usually traces to a shared header/nav/modal component -- "
            "fixing it there resolves it across every page using that "
            "template.",
        ],
    },
    "aria-required-children": {
        "title": "Info and Relationships (ARIA required children)",
        "explanation": (
            "An element has an ARIA role (like 'list' or 'menu') that "
            "requires specific child roles, but those children are "
            "missing -- confusing assistive tech about the structure."
        ),
        "responsible_party": "GovTech Vendor",
        "fix_steps": [
            "Usually caused by the platform's shared template markup, not "
            "page content -- report to the CMS/platform vendor "
            "(CivicPlus, etc.) rather than trying to patch per-page.",
        ],
    },
    "list": {
        "title": "Info and Relationships (List structure)",
        "explanation": (
            "A <ul>/<ol> contains elements other than <li>, breaking the "
            "list semantics screen readers use to announce item counts."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Move any non-<li> content (like a <div> wrapper) outside the "
            "list, or convert it to a properly nested <li>.",
        ],
    },
    "listitem": {
        "title": "Info and Relationships (Orphaned list item)",
        "explanation": (
            "An <li> exists outside of a <ul>/<ol>/<menu> parent, so it's "
            "not announced as part of a list."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Wrap the orphaned <li> in its intended <ul> or <ol> parent.",
        ],
    },
    "target-size": {
        "title": "Target Size (Minimum)",
        "explanation": (
            "A tappable control (button/link) is smaller than 24x24px "
            "or too close to neighboring targets, making it hard to tap "
            "accurately on touchscreens or for users with motor "
            "impairments."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Increase padding/min-width/min-height on the control via CSS, "
            "or add spacing between adjacent tappable elements.",
        ],
    },
    "frame-title": {
        "title": "Frames (Missing title)",
        "explanation": (
            "An <iframe> has no title attribute, so screen reader users "
            "hear 'frame' with no indication of what it contains."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Add a descriptive title attribute to every <iframe>, e.g. "
            "title=\"Township meeting calendar\".",
        ],
    },
    "link-in-text-block": {
        "title": "Use of Color (Link distinguishability)",
        "explanation": (
            "A link within a paragraph is only distinguishable from "
            "surrounding text by color, which fails for colorblind users "
            "or anyone viewing the page in grayscale/high-contrast mode."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Add an underline (or another non-color cue like bold) to "
            "inline links via CSS, in addition to the color change.",
        ],
    },
    "label-content-name-mismatch": {
        "title": "Name, Role, Value (Label mismatch)",
        "explanation": (
            "An element's visible text label doesn't match its "
            "accessible name, so voice-control users saying the visible "
            "label can't activate the control."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Ensure aria-label (if present) contains the same text as, or "
            "starts with, the visible label text.",
        ],
    },
    "td-has-header": {
        "title": "Info and Relationships (Table headers)",
        "explanation": (
            "Cells in a large data table aren't associated with column/row "
            "headers, so screen reader users lose context when navigating "
            "cell by cell."
        ),
        "responsible_party": "Web Developer",
        "fix_steps": [
            "Add scope=\"col\"/scope=\"row\" to <th> elements, or use "
            "headers/id attributes to explicitly associate each <td> "
            "with its header(s).",
        ],
    },
}

# Rule ids seen in the data with no dedicated entry yet fall back to this.
DEFAULT_ENTRY = {
    "title": "(Not yet documented)",
    "explanation": "See the linked WCAG success criterion for details.",
    "responsible_party": "Web Developer",
    "fix_steps": ["Consult WCAG 2.1 documentation for this specific rule."],
}


def lookup(rule_id: str) -> dict:
    """Returns the remediation entry for a rule id, or a documented default."""
    return REMEDIATION_GUIDE.get(rule_id, DEFAULT_ENTRY)


def enrich_dataframe(df: pd.DataFrame, rule_column: str = "WCAG_Success_Criterion") -> pd.DataFrame:
    """Adds Explanation / Responsible_Party / Fix_Steps columns to a
    findings DataFrame (e.g. master_appendix.csv) based on rule_column."""
    df = df.copy()
    entries = df[rule_column].apply(lookup)
    df["Issue_Title"] = entries.apply(lambda e: e["title"])
    df["Explanation"] = entries.apply(lambda e: e["explanation"])
    df["Responsible_Party"] = entries.apply(lambda e: e["responsible_party"])
    df["Fix_Steps"] = entries.apply(lambda e: " | ".join(e["fix_steps"]))
    return df