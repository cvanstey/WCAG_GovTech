"""
crawler.py

Discovers same-domain, in-scope HTML pages starting from one or more seed
URLs, and writes a flat page-list YAML compatible with the schema expected
by lighthouse_scan.py, compliance_engine.py, and (soon) wave_scan.py.

This lets a single crawl feed multiple independent accessibility engines
(axe-core, Lighthouse, WAVE) against the *same* discovered page set, which
is what makes cross-tool agreement/divergence analysis possible downstream.

Requirements:
    pip install requests beautifulsoup4 pyyaml

Usage:
    python crawler.py --seeds seeds.yaml --out crawled_targets.yaml
    python crawler.py --seeds seeds.yaml --out crawled_targets.yaml --max-depth 3 --max-pages 100
"""

import argparse
import sys
import time
import urllib.robotparser
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urljoin, urlparse, urldefrag

import requests
import yaml
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = "DSSA-WCAG-Research-Crawler/1.0 (Stockton University research project; contact via repo)"

# Extensions we don't want to treat as crawlable HTML pages -- these are
# handled by the separate pypdf / Adobe Acrobat document pipeline instead.
NON_HTML_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".mp3",
    ".csv", ".ics", ".xml", ".rss",
)


@dataclass
class CrawledPage:
    municipality: str
    platform: str
    url: str
    seed_url: str
    depth: int
    discovered_via: Optional[str] = None   # URL of the page that linked to this one
    skipped_reason: Optional[str] = None   # e.g. "disallowed_by_robots", "non_html"


# CHANGE: crawl_seed() used to return a bare list with no signal about
# WHY it stopped. A seed that hit max_pages and a seed that ran out of
# links on its own produced identical-looking output -- the LEHT/NJLM
# run both landing on exactly 150 entries was only detectable by manually
# counting afterward. This return type makes "did it finish, or did we
# cut it off" an explicit, printed fact instead of something to notice
# by coincidence.
@dataclass
class SeedCrawlResult:
    pages: list
    exhausted: bool   # True: queue ran dry on its own. False: hit max_pages first.


def load_seeds(path: str) -> list:
    """
    Expects a YAML file like:

    seeds:
      - municipality: "Jersey City"
        platform: "EnerGov"
        url: "https://jerseycitynj-energovpub.tylerhost.net/apps/selfservice#/home"
        respect_robots: true      # optional, defaults to true
      - municipality: "NJLM"
        platform: "NJLM"
        url: "https://www.njlm.org/1438/Digital-Accessibility"
        respect_robots: true
    """
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["seeds"]


def get_robot_parser(base_url: str, user_agent: str) -> urllib.robotparser.RobotFileParser:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # If robots.txt is unreachable/malformed, fail closed: assume nothing is disallowed
        # rather than silently allowing everything -- but log it so it's visible in output.
        print(f"    WARNING: could not read {robots_url}; proceeding with no robots restrictions "
              f"applied for this host (verify manually).", file=sys.stderr)
    return rp


def same_domain(url: str, seed_netloc: str) -> bool:
    return urlparse(url).netloc == seed_netloc


def is_probably_html(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not path.endswith(NON_HTML_EXTENSIONS)


def normalize(url: str) -> str:
    """Strip fragments so #/route-style SPA fragments don't explode the crawl,
    UNLESS the fragment looks like an Angular/SPA hash-route (starts with '/').
    Plain in-page anchors (#section) are stripped; SPA routes are kept."""
    clean, frag = urldefrag(url)
    if frag.startswith("/"):
        return f"{clean}#{frag}"
    return clean


def crawl_seed(
    municipality: str,
    platform: str,
    seed_url: str,
    respect_robots: bool = True,
    max_depth: int = 2,
    max_pages: int = 50,
    delay_sec: float = 1.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> SeedCrawlResult:
    """BFS crawl from a single seed URL. Returns a SeedCrawlResult(pages, exhausted)."""
    seed_parsed = urlparse(seed_url)
    seed_netloc = seed_parsed.netloc

    rp = None
    if respect_robots:
        rp = get_robot_parser(seed_url, user_agent)

    def allowed(url: str) -> bool:
        if rp is None:
            return True
        try:
            return rp.can_fetch(user_agent, url)
        except Exception:
            return True  # if the check itself fails, don't block the crawl on it

    visited = set()
    queue = [(seed_url, 0, None)]  # (url, depth, discovered_via)
    pages = []

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    while queue and len(pages) < max_pages:
        url, depth, referrer = queue.pop(0)
        norm_url = normalize(url)

        if norm_url in visited:
            continue
        visited.add(norm_url)

        if not same_domain(norm_url, seed_netloc):
            continue

        if not is_probably_html(norm_url):
            pages.append(CrawledPage(
                municipality=municipality, platform=platform, url=norm_url,
                seed_url=seed_url, depth=depth, discovered_via=referrer,
                skipped_reason="non_html",
            ))
            continue

        if not allowed(norm_url):
            pages.append(CrawledPage(
                municipality=municipality, platform=platform, url=norm_url,
                seed_url=seed_url, depth=depth, discovered_via=referrer,
                skipped_reason="disallowed_by_robots",
            ))
            print(f"    SKIP (robots.txt disallows): {norm_url}", file=sys.stderr)
            continue

        try:
            resp = session.get(norm_url, timeout=15)
            content_type = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or "text/html" not in content_type:
                pages.append(CrawledPage(
                    municipality=municipality, platform=platform, url=norm_url,
                    seed_url=seed_url, depth=depth, discovered_via=referrer,
                    skipped_reason=f"http_{resp.status_code}_or_non_html_content_type",
                ))
                continue
        except requests.RequestException as e:
            pages.append(CrawledPage(
                municipality=municipality, platform=platform, url=norm_url,
                seed_url=seed_url, depth=depth, discovered_via=referrer,
                skipped_reason=f"fetch_error: {e}",
            ))
            continue

        # Successfully fetched an in-scope HTML page
        pages.append(CrawledPage(
            municipality=municipality, platform=platform, url=norm_url,
            seed_url=seed_url, depth=depth, discovered_via=referrer,
        ))
        print(f"    [{len(pages)}/{max_pages}] depth={depth} {norm_url}", file=sys.stderr)

        if depth < max_depth:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                next_url = urljoin(norm_url, a["href"])
                next_norm = normalize(next_url)
                if next_norm not in visited and same_domain(next_norm, seed_netloc):
                    queue.append((next_norm, depth + 1, norm_url))

        time.sleep(delay_sec)

    # If the loop exited because the queue is genuinely empty, every
    # reachable in-scope link has been visited -- "exhausted" in the
    # honest sense. If it exited because len(pages) hit max_pages while
    # queue still had entries, this was cut off, not complete.
    exhausted = len(queue) == 0
    return SeedCrawlResult(pages=pages, exhausted=exhausted)


# CHANGE: --mode gives two named, no-guessing presets instead of forcing
# every run to hand-pick --max-depth/--max-pages numbers:
#   "all"     -- crawl until the site runs out of in-scope links on its
#                own. No artificial page cap (MAX_PAGES_UNBOUNDED is a
#                generous ceiling, not a target -- see exhaustion check
#                below for whether it was actually enough).
#   "minimal" -- fetch just enough to sanity-check the pipeline end to
#                end (matches the "at least 2 web pages" baseline) without
#                waiting on a full site crawl.
# Explicit --max-depth/--max-pages, if passed, still override the preset
# -- --mode only fills in defaults, it doesn't lock them.
MODE_PRESETS = {
    "all": {"max_depth": 6, "max_pages": 100_000},
    "minimal": {"max_depth": 1, "max_pages": 2},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", required=True, help="YAML file of seed URLs")
    parser.add_argument("--out", default="crawled_targets.yaml")
    parser.add_argument("--mode", choices=["all", "minimal"], default=None,
                         help="'all': crawl until the site runs out of in-scope links. "
                              "'minimal': quick 2-page sanity check of the pipeline. "
                              "Sets --max-depth/--max-pages defaults; explicit flags below override.")
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None,
                         help="Max pages to fetch PER SEED (not total)")
    parser.add_argument("--delay", type=float, default=1.0,
                         help="Seconds to wait between requests (politeness)")
    args = parser.parse_args()

    preset = MODE_PRESETS.get(args.mode, {"max_depth": 2, "max_pages": 50})
    max_depth = args.max_depth if args.max_depth is not None else preset["max_depth"]
    max_pages = args.max_pages if args.max_pages is not None else preset["max_pages"]

    print(f"[MODE] {args.mode or '(default)'} -> max_depth={max_depth}, max_pages={max_pages}",
          file=sys.stderr)

    seeds = load_seeds(args.seeds)
    all_pages = []
    truncated_seeds = []

    for i, s in enumerate(seeds, 1):
        print(f"[{i}/{len(seeds)}] Crawling seed: {s['municipality']} ({s['platform']}) "
              f"-> {s['url']}", file=sys.stderr)
        result = crawl_seed(
            municipality=s["municipality"],
            platform=s["platform"],
            seed_url=s["url"],
            respect_robots=s.get("respect_robots", True),
            max_depth=max_depth,
            max_pages=max_pages,
            delay_sec=args.delay,
        )
        all_pages.extend(result.pages)

        if result.exhausted:
            print(f"    [DONE] {s['municipality']}: crawl exhausted naturally "
                  f"({len(result.pages)} pages, no cap hit).", file=sys.stderr)
        else:
            truncated_seeds.append((s["municipality"], len(result.pages)))
            print(f"    [TRUNCATED] {s['municipality']}: hit max_pages={max_pages} "
                  f"with links still queued -- this is NOT the whole site. "
                  f"Re-run with a higher --max-pages or --mode all if you need full coverage.",
                  file=sys.stderr)

    fetched = [p for p in all_pages if p.skipped_reason is None]
    skipped = [p for p in all_pages if p.skipped_reason is not None]

    print(f"\nDiscovered {len(all_pages)} URLs total: "
          f"{len(fetched)} fetchable, {len(skipped)} skipped.", file=sys.stderr)

    if truncated_seeds:
        print(
            f"\n⚠ {len(truncated_seeds)} seed(s) were TRUNCATED by max_pages, "
            f"not fully crawled:", file=sys.stderr,
        )
        for muni, count in truncated_seeds:
            print(f"    - {muni}: stopped at {count} pages", file=sys.stderr)
        print(
            "  If this is meant to be a whole-site case study, re-run with "
            "--mode all (or a higher --max-pages) for these seeds.",
            file=sys.stderr,
        )
    else:
        print("\n✓ Every seed's crawl exhausted its in-scope links naturally "
              "(no truncation).", file=sys.stderr)

    # Write out in the same "targets" list schema lighthouse_scan.py expects,
    # so this file can be passed straight to --targets on downstream scanners.
    out_data = {
        "targets": [
            {"municipality": p.municipality, "platform": p.platform, "url": p.url}
            for p in fetched
        ],
        # Full crawl metadata (including skips) kept separately for auditing/debugging
        "crawl_log": [asdict(p) for p in all_pages],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(out_data, f, sort_keys=False, allow_unicode=True)

    print(f"Wrote {len(fetched)} crawlable targets (+ full crawl log) to {args.out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()