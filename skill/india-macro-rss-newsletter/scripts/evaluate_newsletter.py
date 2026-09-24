#!/usr/bin/env python3
"""Content and formatting checks for an RSS-first India Macro newsletter."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path


LOW_SIGNAL = (
    "stock to buy", "share price", "dividend", "gadget review", "smartphone review", "open market operation", "omo sale", "stock market prediction", "underwriting auction", "government securities",
    "expected specs", "auction result", "vrrr", "money market operations",
)


def text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def fingerprint(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def report(level: str, message: str, findings: list[tuple[str, str]]) -> None:
    findings.append((level, message))


def evaluate(html_path: Path, audit_path: Path) -> int:
    document = html_path.read_text(encoding="utf-8")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    findings: list[tuple[str, str]] = []
    selected = [item for section in ("macro", "national", "tech") for item in audit.get("selected", {}).get(section, [])]
    market_tape = audit.get("market_tape", {})
    required_quotes = {"Nifty 50", "Sensex", "USD/INR", "Brent"}
    if not market_tape or not required_quotes.issubset(market_tape.get("quotes", {})):
        report("FAIL", "Market Tape snapshot is missing or incomplete.", findings)
    if "Yahoo Finance price data" not in document:
        report("FAIL", "Market Tape source attribution is missing.", findings)

    if audit.get("hours", 49) > 48:
        report("FAIL", "Audit window exceeds 48 hours.", findings)
    cutoff = datetime.fromisoformat(audit["cutoff"])
    for item in selected:
        if datetime.fromisoformat(item["published_at"]) < cutoff:
            report("FAIL", f"Out-of-window selection: {item['title']}", findings)

    seen_titles: set[str] = set()
    for item in selected:
        title = item["title"]
        key = fingerprint(title)
        if key in seen_titles:
            report("FAIL", f"Duplicate selected story: {title}", findings)
        seen_titles.add(key)
        if any(term in title.lower() for term in LOW_SIGNAL):
            report("FAIL", f"Low-signal story passed selection: {title}", findings)

    if not selected:
        report("FAIL", "No selected RSS items in the audit.", findings)
    if len(selected) > 6:
        report("WARN", "More than six editorial stories reduces scanability.", findings)

    required_sections = ("Market tape", "Macro", "National &amp; Strategy", "India Tech", "Tomorrow’s catalysts")
    for section in required_sections:
        if section not in document:
            report("FAIL", f"Missing required section: {section}", findings)
    if document.count("Tomorrow’s catalysts") != 1:
        report("FAIL", "Tomorrow’s catalysts must appear exactly once.", findings)
    if document.find("Tomorrow’s catalysts") < document.find("India Tech"):
        report("FAIL", "Catalysts must follow India Tech.", findings)
    if "@media (max-width" not in document or ":focus-visible" not in document:
        report("WARN", "Responsive or keyboard-focus styling is missing.", findings)

    why_notes = re.findall(r'<p class="why">(.*?)</p>', document, flags=re.DOTALL)
    if len(why_notes) != len(selected):
        report("FAIL", f"Expected {len(selected)} Why it matters notes, found {len(why_notes)}.", findings)
    seen_notes: set[str] = set()
    for note in why_notes:
        clean = text(note)
        words = clean.replace("Why it matters", "").split()
        if len(words) < 18:
            report("FAIL", f"Why it matters is too thin: {clean}", findings)
        if clean.count(".") < 2:
            report("FAIL", f"Why it matters needs two sentences: {clean}", findings)
        key = fingerprint(clean)
        if key in seen_notes:
            report("FAIL", f"Duplicate Why it matters note: {clean}", findings)
        seen_notes.add(key)

    for item in selected:
        if item["link"] not in document:
            report("FAIL", f"Selected source link does not appear in HTML: {item['link']}", findings)

    if "Open the source for the full report." in document:
        report("FAIL", "Placeholder source filler remains in the newsletter.", findings)

    for level, message in findings:
        print(f"{level}: {message}")
    failures = sum(level == "FAIL" for level, _ in findings)
    warnings = sum(level == "WARN" for level, _ in findings)
    print(f"RESULT: {'PASS' if failures == 0 else 'FAIL'} · {failures} failed · {warnings} warnings")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate an RSS-first India Macro newsletter")
    parser.add_argument("html", type=Path)
    parser.add_argument("audit", type=Path)
    args = parser.parse_args()
    raise SystemExit(evaluate(args.html, args.audit))
