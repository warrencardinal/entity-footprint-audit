#!/usr/bin/env python3
"""Entity Footprint Audit

Audit personal-brand or company profile URLs for basic entity/SEO consistency.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (compatible; EntityFootprintAudit/1.0; "
    "+https://warrencardinal.com/)"
)


@dataclass
class AuditResult:
    platform: str
    input_url: str
    status: str
    final_url: str
    page_title: str
    canonical_url: str
    name_found: str
    domain_found: str
    indexable: str
    outbound_link: str
    result: str
    notes: str


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def normalize_domain(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    host = urlparse(value).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def text_contains(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return needle.casefold() in haystack.casefold()


def find_canonical(soup: BeautifulSoup, base_url: str) -> str:
    tag = soup.find(
        "link",
        rel=lambda value: value
        and "canonical"
        in [x.lower() for x in (value if isinstance(value, list) else [value])],
    )
    if tag and tag.get("href"):
        return tag.get("href", "").strip()
    return ""


def is_indexable(response: requests.Response, soup: BeautifulSoup) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    x_robots = response.headers.get("X-Robots-Tag", "")
    if re.search(r"\b(noindex|none)\b", x_robots, flags=re.I):
        reasons.append(f"X-Robots-Tag: {x_robots}")

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        if name in {"robots", "googlebot", "bingbot"}:
            content = meta.get("content", "")
            if re.search(r"\b(noindex|none)\b", content, flags=re.I):
                reasons.append(f"{name} meta: {content}")

    return (not reasons, reasons)


def has_outbound_link(soup: BeautifulSoup, expected_domain: str) -> bool:
    target = normalize_domain(expected_domain)
    if not target:
        return False

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href:
            continue
        parsed = urlparse(href if "://" in href else "https://" + href.lstrip("/"))
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host == target or host.endswith("." + target):
            return True
    return False


def classify(
    status_code: Optional[int],
    name_found: bool,
    domain_found: bool,
    indexable: bool,
    outbound: bool,
) -> str:
    if status_code is None or status_code in {404, 410}:
        return "DEAD"
    if status_code >= 500:
        return "FIX"
    if status_code >= 400:
        return "FIX"
    if status_code < 200 or status_code >= 400:
        return "FIX"
    if all([name_found, domain_found, indexable, outbound]):
        return "GOOD"
    return "FIX"


def audit_profile(session: requests.Session, row: dict[str, str], timeout: int) -> AuditResult:
    platform = (row.get("platform") or "").strip()
    url = (row.get("url") or "").strip()
    expected_name = (row.get("expected_name") or "").strip()
    expected_domain = (row.get("expected_domain") or "").strip()

    notes: list[str] = []

    if not url:
        return AuditResult(
            platform=platform,
            input_url=url,
            status="",
            final_url="",
            page_title="",
            canonical_url="",
            name_found="no",
            domain_found="no",
            indexable="unknown",
            outbound_link="no",
            result="DEAD",
            notes="Missing URL",
        )

    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        status_code = response.status_code
        final_url = response.url
        status = str(status_code)

        if response.history:
            notes.append(f"redirects={len(response.history)}")

        content_type = response.headers.get("Content-Type", "")
        html = (
            response.text
            if "html" in content_type.lower() or response.text.lstrip().startswith("<")
            else ""
        )
        soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")

        title_tag = soup.find("title")
        page_title = title_tag.get_text(" ", strip=True) if title_tag else ""
        canonical_url = find_canonical(soup, final_url)

        visible_text = soup.get_text(" ", strip=True)
        raw_html = html

        name_found = text_contains(visible_text, expected_name) or text_contains(
            raw_html, expected_name
        )
        domain_found = text_contains(raw_html, expected_domain)
        outbound = has_outbound_link(soup, expected_domain)
        indexable, index_reasons = is_indexable(response, soup)

        if index_reasons:
            notes.extend(index_reasons)
        if status_code in {401, 403, 429}:
            notes.append("Site may be blocking automated requests")
        if not html:
            notes.append(
                f"Non-HTML or unreadable response: {content_type or 'unknown content type'}"
            )

        result = classify(status_code, name_found, domain_found, indexable, outbound)

        return AuditResult(
            platform=platform,
            input_url=url,
            status=status,
            final_url=final_url,
            page_title=page_title,
            canonical_url=canonical_url,
            name_found=yes_no(name_found),
            domain_found=yes_no(domain_found),
            indexable=yes_no(indexable),
            outbound_link=yes_no(outbound),
            result=result,
            notes="; ".join(notes),
        )

    except requests.RequestException as exc:
        return AuditResult(
            platform=platform,
            input_url=url,
            status="ERROR",
            final_url="",
            page_title="",
            canonical_url="",
            name_found="no",
            domain_found="no",
            indexable="unknown",
            outbound_link="no",
            result="DEAD",
            notes=str(exc),
        )


def read_profiles(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"platform", "url", "expected_name", "expected_domain"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing required CSV columns: " + ", ".join(sorted(missing)))
        return list(reader)


def write_results(path: Path, results: list[AuditResult]) -> None:
    fieldnames = list(AuditResult.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit profile URLs for entity and SEO consistency."
    )
    parser.add_argument("input", help="CSV file containing profile URLs")
    parser.add_argument(
        "-o",
        "--output",
        default="audit_results.csv",
        help="Output CSV path (default: audit_results.csv)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 2

    try:
        profiles = read_profiles(input_path)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
        }
    )

    results: list[AuditResult] = []
    for i, profile in enumerate(profiles, start=1):
        label = profile.get("platform") or profile.get("url") or f"row {i}"
        print(f"[{i}/{len(profiles)}] Checking {label}...")
        results.append(audit_profile(session, profile, args.timeout))

    write_results(output_path, results)

    good = sum(r.result == "GOOD" for r in results)
    fix = sum(r.result == "FIX" for r in results)
    dead = sum(r.result == "DEAD" for r in results)

    print(f"\nDone. Results written to {output_path}")
    print(f"GOOD: {good} | FIX: {fix} | DEAD: {dead}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
