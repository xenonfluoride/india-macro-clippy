#!/usr/bin/env python3
"""Build the India Macro Clippy editorial sections from selected RSS feeds.

The script uses only RSS/Atom endpoints for news. It accepts no search results,
keeps items published in the preceding 48 hours, normalises duplicates, and writes
both an audit JSON file and the rendered newsletter HTML.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
HTML_PATH = OUTPUTS / "india-macro-clippy.html"
AUDIT_PATH = OUTPUTS / "india-macro-clippy-data.json"
USER_AGENT = "IndiaMacroClippy/1.0 RSS reader (personal newsletter)"

FEEDS = (
    ("Business Standard Economy & Policy", "macro", "https://www.business-standard.com/rss/economy-policy-102.rss"),
    ("Business Standard Companies", "macro", "https://www.business-standard.com/rss/companies-101.rss"),
    ("Economic Times Economy", "macro", "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("The Hindu Economy", "macro", "https://www.thehindu.com/business/Economy/feeder/default.rss"),
    ("Mint Markets", "macro", "https://www.livemint.com/rss/markets"),
    ("The Hindu National", "national", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("Economic Times Tech", "tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"),
    ("The Hindu Technology", "tech", "https://www.thehindu.com/sci-tech/technology/feeder/default.rss"),
    ("YourStory", "tech", "https://yourstory.com/feed"),
    ("Inc42", "tech", "https://inc42.com/feed/"),
)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass(frozen=True)
class FeedItem:
    source: str
    section: str
    title: str
    link: str
    published_at: str
    summary: str


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, *names: str) -> str:
    wanted = set(names)
    for child in list(node):
        if local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return ""


def item_link(node: ET.Element) -> str:
    for child in list(node):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        if child.text:
            return child.text.strip()
    return ""


def plain_text(value: str) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value))
    return parser.text()


def parse_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        iso = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_feed(source: str, section: str, url: str) -> tuple[list[FeedItem], str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
        root = ET.fromstring(payload)
    except Exception as error:  # Feeds should fail independently, not halt a build.
        return [], f"{type(error).__name__}: {error}"

    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    items: list[FeedItem] = []
    for entry in entries:
        title = plain_text(child_text(entry, "title"))
        link = item_link(entry)
        published = child_text(entry, "pubdate", "published", "updated", "date")
        timestamp = parse_timestamp(published)
        summary = plain_text(child_text(entry, "description", "summary", "content", "encoded"))
        if not title or not link or timestamp is None:
            continue
        items.append(
            FeedItem(
                source=source,
                section=section,
                title=title,
                link=link,
                published_at=timestamp.isoformat(),
                summary=summary,
            )
        )
    return items, None


def fingerprint(item: FeedItem) -> str:
    return re.sub(r"[^a-z0-9]+", "", item.title.lower())


def dedupe(items: Iterable[FeedItem]) -> list[FeedItem]:
    seen: set[str] = set()
    result: list[FeedItem] = []
    for item in sorted(items, key=lambda row: row.published_at, reverse=True):
        key = fingerprint(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


SOURCE_WEIGHT = {
    "Business Standard Economy & Policy": 8,
    "Business Standard Companies": 6,
    "Economic Times Economy": 7,
    "The Hindu Economy": 8,
    "The Hindu National": 8,
    "The Print India": 6,
    "Economic Times Tech": 7,
    "The Hindu Technology": 7,
    "Inc42": 8,
    "YourStory": 7,
    "Mint Markets": 5,
}

ROUTINE_MACRO = (
    "auction result", "vrrr", "money market operations", "variable rate reverse repo",
    "treasury bills", "premature redemption", "conversion/switch", "stock to buy", "stocks to buy", "adani total gas", "stocks performed", "gift nifty", "sensex, nifty today", "weekly funding rundown", "next big test", "youth-driven talent", "will build next", "share price",
    "gmp", "dividend", "technical view", "live:", "record date", "open market operation", "stock market prediction", "prediction tomorrow", "outlook for", "cues to watch", "cut-offs", "certificate of registration", "surrender their certificate", "omo sale", "detailed result:", "underwriting auction", "ipo listing", "draft ipo", "draft red herring", "drhp", "price band", "growth forecast", "growth projections", "growth outlook",
)
STOCK_PREDICTION = (
    "prediction", "outlook", "target price", "price target", "stock recommendations",
    "stock to buy", "should investors", "should you", "buy the dip", "bull case",
    "bear case", "stop-loss",
)
NATIONAL_SIGNALS = (
    "cabinet", "parliament", "ministry", "government", "policy", "bill", "act",
    "court", "constitution", "election", "security", "defence", "defense", "border",
    "diplomat", "foreign", "bilateral", "multilateral", "treaty", "unsc", "strategic",
)
NATIONAL_LOW_SIGNAL = (
    "live updates", "gold rate", "weather", "gang-rape", "murder", "accident",
    "hit-and-run", "celebrity", "cricket", "movie", "school students", "hyperactive on the street",
)
MACRO_TOPICS = {
    "food-prices": ("palm oil", "soya oil", "sunflower oil", "edible oil", "onion"),
    "energy": ("crude", "oil", "refiner", "russian cargo", "russia cargo"),
    "external-finance": ("fcnr", "forex", "swap facility", "ecb", "ofcb"),
    "trade": ("trade", "tariff", "fta", "cepa", "duty-free"),
    "credit-allocation": ("project viability", "collateral to cash flows", "cash flows"),
    "digital-payments": ("digital rupee", "cbdc"),
    "monetary-policy": ("rbi", "liquidity", "interest rate", "bond yield"),
    "markets": ("derivatives", "nifty", "sensex", "ipo"),
}
CONSUMER_TECH = (
    "review", "price", "expected specs", "launch date", "headsets",
    "smartphone accessories", "galaxy tab", "redmi note", "rollout begins",
    "daily roundup", "quotes that", "how to claim", "weekly funding rundown", "next big test", "youth-driven talent", "will build next",
)
MACRO_SIGNALS = (
    "rbi", "sebi", "rupee", "inflation", "liquidity", "rate", "yield",
    "fed", "crude", "oil", "nifty", "sensex", "market", "ipo", "upi",
    "bank", "bond", "foreign", "fii", "dii", "trade", "tariff", "growth",
    "economy", "economic", "manufacturing",
)
TECH_SIGNALS = (
    "ai", "agent", "semiconductor", "chip", "deeptech", "upi", "payment",
    "fund", "funding", "raises", "ipo", "regulation", "privacy", "antitrust",
    "data", "cloud", "startup", "software", "robot", "automation", "microsoft",
    "openai", "anthropic", "meta", "google", "amazon", "jio",
)
INDIA_TERMS = (
    "india", "indian", "rbi", "sebi", "upi", "jio", "modi", "bengaluru",
    "mumbai", "delhi", "rupee", "nifty", "sensex", "phonepe", "paytm",
)


def has_any(text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def topic_for(item: FeedItem) -> str | None:
    if item.section != "macro":
        return None
    text = f"{item.title} {item.summary}".lower()
    return next((topic for topic, phrases in MACRO_TOPICS.items() if has_any(text, phrases)), None)


def quality_score(item: FeedItem, now: datetime) -> int | None:
    text = f"{item.title} {item.summary}".lower()
    if item.section == "macro":
        if not has_any(text, INDIA_TERMS):
            return None
        if has_any(text, ROUTINE_MACRO) or has_any(text, STOCK_PREDICTION) or not has_any(text, MACRO_SIGNALS):
            return None
    if item.section == "national":
        if has_any(text, NATIONAL_LOW_SIGNAL) or not has_any(text, NATIONAL_SIGNALS):
            return None
    if item.section == "tech":
        if has_any(text, CONSUMER_TECH) or not has_any(text, INDIA_TERMS):
            return None

    signal_words = {"macro": MACRO_SIGNALS, "national": NATIONAL_SIGNALS, "tech": TECH_SIGNALS}[item.section]
    signal_score = min(12, sum(1 for word in signal_words if word in text) * 3)
    if item.section == "macro" and has_any(text, ("project viability", "collateral to cash flows", "cash flows", "palm oil", "soya oil", "sunflower oil", "edible oil")):
        signal_score += 8
    if item.section == "national" and has_any(text, ("jaishankar", "rubio", "sanctions", "foreign affairs")):
        signal_score += 12
    published = datetime.fromisoformat(item.published_at)
    age_hours = max(0.0, (now - published).total_seconds() / 3600)
    freshness_score = max(0, round(8 - age_hours / 6))
    return SOURCE_WEIGHT.get(item.source, 4) + signal_score + freshness_score


def select_items(items: Iterable[FeedItem], section: str, now: datetime, limit: int = 3) -> list[FeedItem]:
    ranked = [(quality_score(item, now), item) for item in items if item.section == section]
    ranked = [(score, item) for score, item in ranked if score is not None]
    ranked.sort(key=lambda row: (row[0], row[1].published_at), reverse=True)

    selected: list[FeedItem] = []
    used_sources: set[str] = set()
    used_topics: set[str] = set()
    for _, item in ranked:
        if item.source in used_sources:
            continue
        topic = topic_for(item)
        if topic and topic in used_topics:
            continue
        selected.append(item)
        used_sources.add(item.source)
        if topic:
            used_topics.add(topic)
        if len(selected) == limit:
            break
    return selected


def compact(value: str, limit: int = 250) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    shortened = value[: limit + 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{shortened}…"


def display_title(value: str) -> str:
    """Drop publisher-style tails without rewriting the reporter's headline."""
    value = re.split(r"\s+[|—–]\s+", value, maxsplit=1)[0].strip()
    value = re.sub(r"\s*:\s*Check (?:stock )?performance$", "", value, flags=re.IGNORECASE)
    value = re.sub(r":\s*(?:Is|What|How|Why|Check|Everything)\b.*$", "", value, flags=re.IGNORECASE)
    return value


def why_it_matters(item: FeedItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if item.section == "macro":
        if has_any(text, ("palm oil", "soya oil", "sunflower oil", "edible oil")):
            return "Lower import duties reduce the landed cost of key cooking oils, creating room for retail prices to ease. Watch pass-through at the shelf and whether protections for domestic oilseed growers become the next policy trade-off."
        if has_any(text, ("omcs", "oil marketing companies", "fuel losses", "under-recoveries")):
            return "Fuel under-recoveries transfer a crude-price shock from consumers to state-owned refiners and their balance sheets. Watch for retail-price changes, compensation, or a further rise in daily losses if international oil stays elevated."
        if has_any(text, ("india-new zealand", "india-new zealand", "new zealand fta")):
            return "The tariff schedule gives Indian exporters a defined route into New Zealand while preserving sensitive domestic farm segments. Watch exporter use of the concessions after the agreement takes effect and the remaining exclusions in agricultural trade."
        if has_any(text, ("project viability", "collateral to cash flows", "cash flows")):
            return "Moving credit appraisal toward project cash flows would direct lending toward long-duration investment rather than collateral-heavy borrowers. Watch whether banks change underwriting and whether infrastructure and manufacturing projects gain financing on those terms."
        if has_any(text, ("digital rupee", "cbdc")):
            return "Adding rewards, corporate payouts, and offline use cases is an attempt to make the digital rupee useful beyond basic settlement. Watch for merchant integration and repeat transaction use before treating the wallet as a scaled payments rail."
        if has_any(text, ("growth", "manufacturing", "economy", "economic")):
            return "The growth print matters only if demand converts into durable private investment, output, and employment. Watch the next manufacturing and credit data for evidence that the expansion is broadening rather than relying on public spending."
        if has_any(text, ("rupee", "fed", "crude", "oil", "foreign")):
            return "Currency and oil moves change India’s imported-inflation bill and the external-account buffer. Watch USD/INR, crude and foreign flows for confirmation of whether the pressure is easing or broadening."
        if has_any(text, ("rbi", "sebi", "liquidity", "rate", "yield")):
            return "The policy signal affects funding conditions through rates, liquidity, and risk appetite. Watch the next money-market data and lending response to see whether it changes the cost or availability of credit."
        if has_any(text, ("ipo", "nifty", "sensex", "market")):
            return "A broad market move affects financing conditions and household balance sheets beyond any single stock. Watch market breadth and fund flows to distinguish a durable shift from a narrow price reaction."
        return "The development changes incentives for households, firms, or public finances through the channel described in the report. Watch the next official data or implementation decision for evidence that the effect is reaching the real economy."
    if item.section == "national" and has_any(text, ("jaishankar", "rubio", "sanctions")):
        return "Sanctions policy can constrain India’s room to manage energy and defence ties even when bilateral diplomacy remains constructive. Watch the official readout and any waiver or enforcement detail that turns the concern into a commercial constraint."
    if has_any(text, ("semiconductor", "chip", "deeptech")):
        return "Signed customers, deployed capacity, and repeat orders matter more than the announcement. Deep-tech sales cycles can hide weak commercial demand behind a strong launch narrative."
    if has_any(text, ("gcc", "capability center", "capability centres")):
        return "AI pilots do not produce the promised productivity gains until GCCs redesign workflows, data access, and accountability around them. Watch for pilots graduating into production deployments and for reskilling budgets to follow."
    if has_any(text, ("upi", "payment", "fintech")):
        if has_any(text, ("market share", "transaction volumes", "transaction share")):
            return "Navi’s gain tests the staying power of India’s payment incumbents. Watch value share, incentive spending, and merchant retention before calling the shift durable."
        if has_any(text, ("mdr", "pricing", "fee")):
            return "The MDR structure will decide who funds the payment rails and who absorbs the cost. Merchant adoption and regulator guidance will show whether the new charge can stick."
        return "Putting transaction, mandate, complaint, and fraud tasks behind one assistant could reduce the friction of using UPI services. Watch activation and complaint-resolution data to see whether conversational access improves outcomes without raising fraud risk."
    if has_any(text, ("fund", "funding", "raises", "ipo")):
        return "Check customer traction and unit economics before treating the transaction as a sector signal. The next financing round or earnings release will test the valuation behind the headline."
    if has_any(text, ("regulation", "privacy", "antitrust", "data")):
        return "The rule's scope and enforcement will decide which companies carry the cost. Compliance deadlines and exemptions will separate the exposed firms from the beneficiaries."
    if has_any(text, ("fssai", "food safety", "penalis", "non-compliance")):
        return "Penalties make marketplaces accountable for food-safety controls across sellers and quick-commerce fulfilment. Watch the orders’ scope and platform remediation to see whether compliance becomes a material operating cost."
    return "The report identifies a specific operational or regulatory pressure on the companies involved. Watch the first disclosed response or enforcement step to determine whether that pressure changes behaviour."


def refresh_edition(document: str, now: datetime) -> str:
    """Keep the visible edition date aligned with a newly built RSS issue."""
    edition_date = now.strftime("%-d %B %Y")
    match = re.search(r'<p class="issue meta"><strong>Issue (\d+)</strong><br />([^<]+)<br />', document)
    if not match:
        return document
    issue = int(match.group(1)) + (match.group(2).strip() != edition_date)
    document = re.sub(r'<title>India Macro Clippy: .*?</title>', f'<title>India Macro Clippy: {edition_date}</title>', document, count=1)
    document = re.sub(
        r'<p class="issue meta"><strong>Issue \d+</strong><br />[^<]+<br />',
        f'<p class="issue meta"><strong>Issue {issue:03d}</strong><br />{edition_date}<br />',
        document,
        count=1,
    )
    return document


def card(item: FeedItem, number: int) -> str:
    published = datetime.fromisoformat(item.published_at).strftime("%-d %b · %H:%M UTC")
    summary = compact(item.summary, 220)
    why = why_it_matters(item)
    return f'''        <article class="story">
          <div class="story-no">{number:02d}</div>
          <div>
            <h3>{html.escape(display_title(item.title))}</h3>
            {f'<p>{html.escape(summary)}</p>' if summary else ''}
            <p class="why"><span>Why it matters</span><br />{html.escape(why)}</p>
            <p class="source">RSS · <a href="{html.escape(item.link, quote=True)}">{html.escape(item.source)}, {published}</a></p>
          </div>
        </article>'''


def empty_card(section: str) -> str:
    return f'''        <article class="story">
          <div class="story-no">—</div>
          <div>
            <h3>No fresh {section} items passed the filter.</h3>
            <p>This build keeps the 48-hour cutoff hard. Check the feed audit for source errors or the next scheduled refresh.</p>
          </div>
        </article>'''


def replace_region(document: str, name: str, content: str) -> str:
    pattern = rf"(<!-- RSS:{name}:START -->).*?(<!-- RSS:{name}:END -->)"
    result, count = re.subn(pattern, rf"\1\n{content}\n        \2", document, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected one RSS:{name} region, found {count}")
    return result


def render_build(all_items: list[FeedItem], feed_status: list[dict], now: datetime, hours: int, mode: str) -> int:
    cutoff = now - timedelta(hours=hours)
    fresh = [item for item in all_items if datetime.fromisoformat(item.published_at) >= cutoff]
    items = dedupe(fresh)
    macro = select_items(items, "macro", now)
    national = select_items(items, "national", now, limit=1)
    tech = select_items(items, "tech", now)

    audit = {
        "generated_at": now.isoformat(),
        "cutoff": cutoff.isoformat(),
        "hours": hours,
        "mode": mode,
        "feeds": feed_status,
        "items_retained": [asdict(item) for item in items],
        "selected": {
            "macro": [asdict(item) for item in macro],
            "national": [asdict(item) for item in national],
            "tech": [asdict(item) for item in tech],
        },
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not any(row["error"] is None for row in feed_status) or not (macro or tech):
        print("RSS build aborted: no publishable RSS selection; preserved the last good newsletter.", file=sys.stderr)
        return 2

    document = HTML_PATH.read_text(encoding="utf-8")
    document = refresh_edition(document, now)
    document = replace_region("".join(document), "MACRO", "\n".join(card(item, index + 1) for index, item in enumerate(macro)) or empty_card("macro"))
    document = replace_region(document, "NATIONAL", "\n".join(card(item, index + len(macro) + 1) for index, item in enumerate(national)) or empty_card("National &amp; Strategy"))
    document = replace_region(document, "TECH", "\n".join(card(item, index + len(macro) + len(national) + 1) for index, item in enumerate(tech)) or empty_card("tech"))
    stamp = now.strftime("RSS build · %-d %b · %H:%M UTC")
    document, count = re.subn(r'<span id="rss-status">.*?</span>', f'<span id="rss-status">{stamp}</span>', document)
    if count != 1:
        raise ValueError(f"Expected one RSS status element, found {count}")
    HTML_PATH.write_text(document, encoding="utf-8")

    print(f"RSS build complete: {len(macro)} macro, {len(national)} national, {len(tech)} tech, {len(items)} unique fresh items")
    print(f"Audit: {AUDIT_PATH}")
    failed = [row for row in feed_status if row["error"]]
    if failed:
        print(f"Feed fetch failures: {len(failed)}", file=sys.stderr)
    return 0


def build(hours: int) -> int:
    now = datetime.now(timezone.utc)
    all_items: list[FeedItem] = []
    feed_status: list[dict[str, str | int | None]] = []
    for source, section, url in FEEDS:
        items, error = fetch_feed(source, section, url)
        all_items.extend(items)
        feed_status.append({"source": source, "section": section, "url": url, "items_parsed": len(items), "error": error})
    return render_build(all_items, feed_status, now, hours, "live-rss")


def rebuild_from_audit(hours: int) -> int:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    items = [FeedItem(**row) for row in data["items_retained"]]
    return render_build(items, data["feeds"], datetime.now(timezone.utc), hours, "cached-rss")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build India Macro Clippy from RSS feeds")
    parser.add_argument("--hours", type=int, default=48, help="maximum age of included items")
    parser.add_argument("--from-audit", action="store_true", help="rebuild from the most recent successful RSS audit without fetching")
    arguments = parser.parse_args()
    if arguments.hours <= 0:
        parser.error("--hours must be positive")
    raise SystemExit(rebuild_from_audit(arguments.hours) if arguments.from_audit else build(arguments.hours))
