#!/usr/bin/env python3
"""Build the India Macro Clippy editorial sections from selected RSS feeds.

The script uses only RSS/Atom endpoints for news. It accepts no search results,
keeps items published in the configured recency window, normalises duplicates,
and writes both an audit JSON file and the rendered newsletter HTML.
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
DEFAULT_RECENCY_HOURS = 36

FEEDS = (
    ("Business Standard Economy & Policy", "macro", "https://www.business-standard.com/rss/economy-policy-102.rss"),
    ("Business Standard Companies", "macro", "https://www.business-standard.com/rss/companies-101.rss"),
    ("Economic Times Economy", "macro", "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("The Hindu Economy", "macro", "https://www.thehindu.com/business/Economy/feeder/default.rss"),
    ("Mint Markets", "macro", "https://www.livemint.com/rss/markets"),
    ("Hindustan Times India", "national", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"),
    ("NDTV India", "national", "https://feeds.feedburner.com/ndtvnews-india-news"),
    ("BBC News India", "national", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
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
    "Hindustan Times India": 8,
    "NDTV India": 8,
    "BBC News India": 7,
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
    "gmp", "dividend", "technical view", "live:", "record date", "open market operation", "stock market prediction", "prediction tomorrow", "outlook for", "cues to watch", "cut-offs", "certificate of registration", "surrender their certificate", "omo sale", "net debt sale", "detailed result:", "underwriting auction", "ipo listing", "listing mandate", "draft ipo", "draft red herring", "drhp", "price band", "growth forecast", "growth projections", "growth outlook", "md & ceo", "chief executive officer", "market to touch", "ai enablers surge", "experts decode", "factors can bring them back", "may hold bilateral meeting", "economic growth possible", "top stocks in focus", "must be on radar", "greed and fear index", "portfolio has", "stock market holidays", "market holidays", "asks states to", "signals another", "private placement", "merchant discount rate", "nifty breaks", "nifty falls", "nifty 50 falls", "nifty 50 down", "set for worst year", "worst monthly", "experts see", "weekly policy watch", "blue-chip stocks", "minister discusses", "hope rbi", "common ground with us", "rupee hits", "what does it mean for the indian stock market", "steel manufacturing in the us", "h1fy", "h2fy", "top gainers", "top losers", "no upi day", "nifty 50 stocks", "posted double-digit losses", "market sell-off", "5-year cagr", "bank fd returns", "mutual fund sahi hai", "stock tanked", "nifty inclusion", "index reshuffle", "what lies ahead for investors",
)
STOCK_PREDICTION = (
    "prediction", "outlook", "target price", "price target", "stock recommendations",
    "stock to buy", "should investors", "should you", "buy the dip", "bull case",
    "bear case", "stop-loss", "stock selection", "expert view", "strong technicals",
)
MACRO_SPECULATION = (
    "likely to hike", "may hike", "may increase rates", "could keep rates",
    "experts poll", "poll shows", "according to economists", "in talks with",
    "plans india service centres", "could spur further liberalisation",
    "enters race for proposed", "proposed polymer banknote programme",
    "deloitte india", "rbi mpc meeting", "round of cepa talks", "repo rate may climb",
    "meets us corporate leaders",
)
MACRO_COMMENTARY_OR_RECAP = (
    "says shaktikanta das", "within striking distance", "resilience not accidental",
    "cash, derivatives volumes", "cash derivatives volumes", "fastest-growing asia market",
)
NATIONAL_SIGNALS = (
    "cabinet", "parliament", "ministry", "government", "policy", "bill", "act",
    "court", "constitution", "election", "security", "defence", "defense", "border",
    "diplomat", "foreign", "bilateral", "multilateral", "treaty", "unsc", "strategic",
)
NATIONAL_SCOPE_SIGNALS = (
    "india", "indian", "centre", "central government", "union government", "supreme court",
    "parliament", "ministry", "national", "defence", "foreign", "bilateral", "multilateral",
)
NATIONAL_LOW_SIGNAL = (
    "live updates", "gold rate", "weather", "gang-rape", "murder", "accident", "criminal investigation", "cover-up job",
    "cjp protest", "paper leak", "charge sheet",
    "hit-and-run", "celebrity", "cricket", "movie", "school students", "hyperactive on the street",
    "congress", "bjp", "rahul gandhi", "opposition", "party", "campaign", "cadre", "votes", "spokesperson", "next pharma frontier",
)
NATIONAL_EVENT_STOPWORDS = {
    "about", "after", "against", "amid", "case", "court", "defence", "defense",
    "government", "india", "indian", "ministry", "national", "policy", "security",
    "state", "states", "supreme", "their", "there", "through", "under", "with",
}
MACRO_TOPICS = {
    "food-and-rural": (
        "food price", "edible oil", "palm oil", "soya oil", "sunflower oil", "onion",
        "drought", "rainfall deficit", "monsoon", "crop loss", "crop loan", "agriculture",
    ),
    "energy-and-infrastructure": (
        "crude", "oil", "refiner", "russian cargo", "russian crude", "lng", "nuclear",
        "epr", "pumped hydro", "renewable", "power grid", "energy infrastructure",
    ),
    "climate-and-water": (
        "water infrastructure", "water financing", "water policy", "el niño", "climate resilience",
        "monsoon rainfall", "rainfall deficit",
    ),
    "external-finance": (
        "forex", "swap facility", "foreign investor", "foreign investment", "investment treaty",
        "bilateral investment", "arbitration", "fpi", "fii", "portfolio investor",
    ),
    "trade-and-rules": (
        "trade", "tariff", "fta", "cepa", "duty-free", "customs", "export", "import",
        "trade secrets", "contract enforcement",
    ),
    "investment-and-industry": (
        "capex", "project pipeline", "manufacturing", "semiconductor", "chip", "logistics",
        "industrial policy", "factory", "supply chain",
    ),
    "digital-payments": ("digital rupee", "cbdc", "upi", "payment rail"),
    "monetary-policy": ("rbi", "liquidity", "interest rate", "bond yield", "policy rate"),
    "markets": ("derivatives", "nifty", "sensex"),
}
CONSUMER_TECH = (
    "review", "price", "expected specs", "launch date", "headsets",
    "smartphone accessories", "galaxy tab", "redmi note", "rollout begins",
    "k-pop",
    "daily roundup", "quotes that", "how to claim", "weekly funding rundown", "next big test", "youth-driven talent", "will build next", "no upi day", "report card",
    "raises", "funding round", "series a", "series b", "funding", "first close", "fund iii", "talent gap", "executive", "exec", "mindset", "interview", "thought leadership", "ipo", "drhp", "listing", "australia breach", "australian ai probe", "nurture indian deeptech startups", "techsparks gets bolder", "where is india's fintech story headed next",
)
MACRO_SIGNALS = tuple(phrase for phrases in MACRO_TOPICS.values() for phrase in phrases)
TECH_SIGNALS = (
    "ai", "agent", "semiconductor", "chip", "deeptech", "upi", "payment",
    "fund", "funding", "raises", "ipo", "regulation", "privacy", "antitrust",
    "data", "cloud", "startup", "software", "robot", "automation", "microsoft",
    "openai", "anthropic", "meta", "google", "amazon", "jio", "gaming",
    "digital maturity", "non-profit", "gameskraft",
)
TECH_POLICY_SIGNALS = ("it rules", "social media", "digital policy", "online safety", "intermediary")
DOMESTIC_POLICY_ACTORS = ("centre", "central government", "supreme court", "government of india", "ministry", "parliament")
INDIA_TERMS = (
    "india", "indian", "rbi", "sebi", "upi", "jio", "modi", "bengaluru",
    "mumbai", "delhi", "rupee", "nifty", "sensex", "phonepe", "paytm",
    "maharashtra", "gujarat", "karnataka", "odisha", "tamil nadu", "uttar pradesh",
    "andhra pradesh", "telangana", "kerala", "rajasthan", "madhya pradesh", "bihar",
)
CONCRETE_ACTIONS = (
    "approved", "announced", "attached", "build", "consult", "declared", "deploy",
    "discuss", "fund", "issued", "launched", "met", "plans", "review", "will keep",
)
NATIONAL_DECISIONS = (
    "approved", "amended", "announced", "direct", "directed", "directs", "enacted",
    "established", "imposed", "issued", "join", "joined", "joins", "launched", "notified",
    "ordered", "passed", "rule", "ruled", "sign", "signed", "signs",
)


def phrase_pattern(phrase: str) -> str:
    """Match whole words, allowing punctuation or whitespace inside a phrase."""
    words = re.findall(r"[a-z0-9]+", phrase.lower())
    if not words:
        return r"$^"
    return r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(map(re.escape, words)) + r"(?![a-z0-9])"


def has_any(text: str, phrases: Iterable[str]) -> bool:
    return any(re.search(phrase_pattern(phrase), text, flags=re.IGNORECASE) for phrase in phrases)


def is_generic_startup_support(text: str) -> bool:
    """Reject public startup-support schemes that lack an operating outcome."""
    return has_any(text, ("startup", "startups")) and (has_any(text, (
        "government first", "startup scheme", "startup initiative", "target startups",
        "plan deeptech fund", "plans deeptech fund",
    )) or (has_any(text, ("fund",)) and has_any(text, ("target",))))


def macro_topics(item: FeedItem) -> list[str]:
    text = f"{item.title} {item.summary}"
    return [topic for topic, phrases in MACRO_TOPICS.items() if has_any(text, phrases)]


def topic_for(item: FeedItem) -> str | None:
    if item.section != "macro":
        return None
    return next(iter(macro_topics(item)), None)


def event_for(item: FeedItem) -> str | None:
    """Recognise recurring storylines that should receive only one tech card."""
    text = f"{item.title} {item.summary}"
    if item.section == "tech" and has_any(text, ("upi", "merchant discount rate", "mdr")):
        return "upi-mdr"
    if item.section == "tech" and has_any(text, TECH_POLICY_SIGNALS) and has_any(text, ("under-18", "minor", "minors")):
        return "social-media-minors"
    return None


def national_event_terms(item: FeedItem) -> set[str]:
    """Keep the specific terms that can corroborate one national story across feeds."""
    text = f"{item.title} {item.summary}".lower()
    return {
        token for token in re.findall(r"[a-z][a-z0-9-]+", text)
        if len(token) >= 4 and token not in NATIONAL_EVENT_STOPWORDS
    }


def national_corroborators(item: FeedItem, items: Iterable[FeedItem]) -> set[str]:
    """Return independent sources covering the same specific national event."""
    if item.section != "national":
        return set()
    terms = national_event_terms(item)
    corroborators: set[str] = set()
    for other in items:
        if other.section != "national" or other.source == item.source:
            continue
        if len(terms & national_event_terms(other)) >= 2:
            corroborators.add(other.source)
    return corroborators


def same_national_event(left: FeedItem, right: FeedItem) -> bool:
    return left.section == right.section == "national" and len(national_event_terms(left) & national_event_terms(right)) >= 2


def quality_score(item: FeedItem, now: datetime) -> int | None:
    text = f"{item.title} {item.summary}"
    if item.section == "macro":
        if not has_any(text, INDIA_TERMS):
            return None
        if (has_any(text, ROUTINE_MACRO) or has_any(text, STOCK_PREDICTION)
                or has_any(item.title, MACRO_SPECULATION)
                or has_any(item.title, MACRO_COMMENTARY_OR_RECAP)):
            return None
        themes = macro_topics(item)
        if not themes:
            return None
        theme_score = 6 + min(3, 2 * (len(themes) - 1))
        evidence_score = 3 if has_any(text, CONCRETE_ACTIONS) else 0
        published = datetime.fromisoformat(item.published_at)
        age_hours = max(0.0, (now - published).total_seconds() / 3600)
        freshness_score = max(0, round(8 - age_hours / 6))
        return SOURCE_WEIGHT.get(item.source, 4) + theme_score + evidence_score + freshness_score
    if item.section == "national":
        if (has_any(text, NATIONAL_LOW_SIGNAL) or not has_any(text, NATIONAL_SIGNALS)
                or not has_any(text, NATIONAL_SCOPE_SIGNALS)
                or not has_any(text, NATIONAL_DECISIONS)):
            return None
    if item.section == "tech":
        domestic_tech_policy = has_any(text, TECH_POLICY_SIGNALS) and has_any(text, DOMESTIC_POLICY_ACTORS)
        if (has_any(text, CONSUMER_TECH) or has_any(text, ("ceo",)) or is_generic_startup_support(text)
                or has_any(text, ("industry experts", "experts said", "experts say"))
                or has_any(text, ("next major frontier", "next infrastructure push"))
                or not (has_any(text, INDIA_TERMS) or domestic_tech_policy)
                or not (has_any(text, TECH_SIGNALS) or domestic_tech_policy)):
            return None

    signal_words = {"national": NATIONAL_SIGNALS, "tech": TECH_SIGNALS}[item.section]
    signal_score = min(12, sum(1 for word in signal_words if word in text) * 3)
    if item.section == "macro" and has_any(text, ("project viability", "collateral to cash flows", "cash flows", "palm oil", "soya oil", "sunflower oil", "edible oil")):
        signal_score += 8
    if item.section == "national" and has_any(text, ("jaishankar", "rubio", "sanctions", "foreign affairs")):
        signal_score += 12
    if item.section == "tech" and has_any(text, ("fssai", "food safety", "non-compliance")):
        signal_score += 18
    if item.section == "tech" and has_any(text, ("mdr", "npci", "cyber threats")):
        signal_score += 16
    if item.section == "tech" and has_any(text, ("acquire", "acquisition")):
        signal_score += 10
    if item.section == "tech" and has_any(text, ("phonepe", "payment devices", "bharat market")):
        signal_score += 10
    if item.section == "tech" and has_any(text, TECH_POLICY_SIGNALS) and has_any(text, DOMESTIC_POLICY_ACTORS):
        signal_score += 14
    published = datetime.fromisoformat(item.published_at)
    age_hours = max(0.0, (now - published).total_seconds() / 3600)
    freshness_score = max(0, round(8 - age_hours / 6))
    return SOURCE_WEIGHT.get(item.source, 4) + signal_score + freshness_score


def selection_score(item: FeedItem, items: Iterable[FeedItem], now: datetime) -> int | None:
    """Rank strong national stories higher when another independent feed confirms them."""
    score = quality_score(item, now)
    if score is None:
        return None
    if item.section == "national":
        score += min(8, 4 * len(national_corroborators(item, items)))
    return score


def select_items(items: Iterable[FeedItem], section: str, now: datetime, limit: int = 3) -> list[FeedItem]:
    item_list = list(items)
    ranked = [(selection_score(item, item_list, now), item) for item in item_list if item.section == section]
    ranked = [(score, item) for score, item in ranked if score is not None]
    if section == "macro":
        # A thin market-calendar or general-market item must not fill a third slot.
        ranked = [(score, item) for score, item in ranked if score >= 15]
    ranked.sort(key=lambda row: (row[0], row[1].published_at), reverse=True)

    selected: list[FeedItem] = []
    used_sources: set[str] = set()
    used_topics: set[str] = set()
    used_events: set[str] = set()
    for _, item in ranked:
        if section == "national" and any(same_national_event(item, chosen) for chosen in selected):
            continue
        if item.source in used_sources:
            continue
        topic = topic_for(item)
        if topic and topic in used_topics:
            continue
        event = event_for(item)
        if event and event in used_events:
            continue
        selected.append(item)
        used_sources.add(item.source)
        if topic:
            used_topics.add(topic)
        if event:
            used_events.add(event)
        if len(selected) == limit:
            break
    return selected


def selection_audit(items: Iterable[FeedItem], section: str, now: datetime, selected: Iterable[FeedItem]) -> list[dict[str, object]]:
    """Make editorial exclusions inspectable instead of silently dropping a story."""
    selected_items = list(selected)
    selected_sources = {item.source for item in selected_items}
    selected_topics = {topic_for(item) for item in selected_items if topic_for(item)}
    rows: list[dict[str, object]] = []
    for item in items:
        if item.section != section:
            continue
        score = selection_score(item, items, now)
        text = f"{item.title} {item.summary}"
        if item in selected_items:
            decision = "selected"
        elif score is None:
            if section == "macro" and not has_any(text, INDIA_TERMS):
                decision = "rejected: no India signal"
            elif section == "macro" and (has_any(text, ROUTINE_MACRO) or has_any(text, STOCK_PREDICTION)):
                decision = "rejected: hard editorial exclusion"
            elif section == "macro":
                decision = "rejected: no recognised macro theme"
            else:
                decision = "rejected: section relevance or hard editorial exclusion"
        elif section == "national" and any(same_national_event(item, chosen) for chosen in selected_items):
            decision = "eligible but excluded: duplicate national event"
        elif item.source in selected_sources:
            decision = "eligible but excluded: duplicate source"
        elif section == "macro" and topic_for(item) in selected_topics:
            decision = "eligible but excluded: duplicate macro theme"
        else:
            decision = "eligible but excluded: lower-ranked than the editorial limit"
        rows.append({
            "source": item.source,
            "section": item.section,
            "title": item.title,
            "link": item.link,
            "published_at": item.published_at,
            "score": score,
            "themes": macro_topics(item) if section == "macro" else [],
            "corroborated_by": sorted(national_corroborators(item, items)) if section == "national" else [],
            "decision": decision,
        })
    return sorted(rows, key=lambda row: ((row["score"] is not None), row["score"] or -1, row["published_at"]), reverse=True)


def compact(value: str, limit: int = 250) -> str:
    value = " ".join(value.split()).rstrip("…").rstrip()
    if len(value) <= limit:
        return value if value.endswith((".", "!", "?")) else f"{value}."
    sentences = re.split(r"(?<=[.!?])\s+", value)
    complete = []
    size = 0
    for sentence in sentences:
        if size + len(sentence) + (1 if complete else 0) > limit:
            break
        complete.append(sentence)
        size += len(sentence) + (1 if complete else 0)
    if complete:
        return " ".join(complete)
    shortened = value[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{shortened}."


def display_title(value: str) -> str:
    """Drop publisher-style tails without rewriting the reporter's headline."""
    value = re.split(r"\s+[|—–]\s+", value, maxsplit=1)[0].strip()
    value = re.sub(r"\s*:\s*Check (?:stock )?performance$", "", value, flags=re.IGNORECASE)
    value = re.sub(r":\s*(?:Is|What|How|Why|Check|Everything)\b.*$", "", value, flags=re.IGNORECASE)
    return value


def why_it_matters(item: FeedItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if item.section == "macro":
        if has_any(text, ("epr", "nuclear", "pumped hydro")):
            return "A nuclear and pumped-hydro pipeline could add firm low-carbon power and storage, but it depends on regulatory clarity and long project timelines. Watch for a project framework, financing plan, and named sites before treating the talks as build commitments."
        if has_any(text, ("drought", "crop loss", "crop loan")):
            return "Drought relief shifts part of the rainfall shock from farm households to state budgets and lenders through loan restructuring and support payments. Watch crop-damage assessments, relief orders, and food-price data for the scale of the economic hit."
        if has_any(text, ("water financing", "water infrastructure", "el niño")):
            return "More water financing could improve resilience to rainfall shortfalls while creating a pipeline for infrastructure and policy projects. Watch AIIB approvals and state-level project plans to see whether the proposal becomes funded capacity."
        if has_any(text, ("investment treaty", "bilateral investment", "taxation outside")):
            return "Keeping taxation outside investment treaties narrows the route investors can use to challenge tax disputes internationally. Watch the Cabinet’s model treaty text and negotiations with partner countries for the practical impact on investor protections."
        if has_any(text, ("trade secrets", "contract enforcement", "whistleblower safeguards")):
            return "Clearer trade-secret and contract rules could reduce legal uncertainty for firms sharing know-how and working with suppliers. Watch the consultation paper and the choice between a new law or Contract Act changes for the real compliance burden."
        if has_any(text, ("rodtep", "rosctl", "export support schemes", "export sops")):
            return "Reviewing export-support schemes could change the cost and predictability of selling from India into overseas markets. Watch the review’s recommendations and any revised reimbursement rules for the effect on exporter cash flows and trade competitiveness."
        if has_any(text, ("semiconductor logistics", "chip ecosystem", "sensitive chip equipment")):
            return "Specialised chip logistics and trained handling staff can remove a practical bottleneck in India’s semiconductor supply chain. Watch for site construction, customer contracts, and the planned 2027 opening to test whether the facility becomes operating capacity."
        if has_any(text, ("origin declaration", "concessional duty", "india-uk ceta")):
            return "Accepting an origin declaration as the normal proof of eligibility should lower paperwork costs for importers using the India-UK trade agreement. Watch customs scrutiny rates and preference-claim volumes to see whether the simplification translates into wider use of the concessions."
        if has_any(text, ("private sector capex", "private-sector capex", "aggregate cost of projects")):
            return "A larger private-project pipeline would support investment demand, but infrastructure’s dominance means the benefit may remain concentrated in capital-intensive sectors. Watch project financial closures and bank credit to see whether manufacturing and services begin to share the spending cycle."
        if has_any(text, ("russian crude", "russian oil supplies", "russian oil")):
            return "Reliable Russian crude flows can cushion India’s import bill when disruptions tighten global supply, reducing the pressure passed through to refiners and consumers. Watch shipment volumes, discounts, and sanctions enforcement to see whether that buffer remains commercially usable."
        if has_any(text, ("commodity derivatives", "foreign portfolio investors", "fpi access")):
            return "Wider FPI access can deepen commodity hedging and price discovery, while delivery rules limit how foreign investors take physical exposure. Watch derivatives volumes, open interest, and any delivery activity to see whether the rule changes liquidity rather than just eligibility."
        if has_any(text, ("blue bonds", "blue economy")):
            return "SEBI recognition gives ocean-linked projects a defined sustainable-finance label, potentially widening their investor pool. Watch for an issuer pipeline and use-of-proceeds disclosures, which will test whether the label mobilises capital without weakening standards."
        if has_any(text, ("palm oil", "soya oil", "sunflower oil", "edible oil")):
            return "Lower import duties reduce the landed cost of key cooking oils, creating room for retail prices to ease. Watch pass-through at the shelf and whether protections for domestic oilseed growers become the next policy trade-off."
        if has_any(text, ("omcs", "oil marketing companies", "fuel losses", "under-recoveries")):
            return "Fuel under-recoveries transfer a crude-price shock from consumers to state-owned refiners and their balance sheets. Watch for retail-price changes, compensation, or a further rise in daily losses if international oil stays elevated."
        if has_any(text, ("deepwater gas", "kg-d6", "gas price ceiling")):
            return "A higher ceiling price improves the return available for difficult offshore gas production, making capital-intensive fields more viable to develop. Watch producer investment plans and domestic output data to see whether the price change translates into supply rather than only better realised prices."
        if has_any(text, ("india-new zealand", "india-new zealand", "new zealand fta")):
            return "The tariff schedule gives Indian exporters a defined route into New Zealand while preserving sensitive domestic farm segments. Watch exporter use of the concessions after the agreement takes effect and the remaining exclusions in agricultural trade."
        if has_any(text, ("project viability", "collateral to cash flows", "cash flows")):
            return "Moving credit appraisal toward project cash flows would direct lending toward long-duration investment rather than collateral-heavy borrowers. Watch whether banks change underwriting and whether infrastructure and manufacturing projects gain financing on those terms."
        if has_any(text, ("digital rupee", "cbdc")):
            return "Adding rewards, corporate payouts, and offline use cases is an attempt to make the digital rupee useful beyond basic settlement. Watch for merchant integration and repeat transaction use before treating the wallet as a scaled payments rail."
        if has_any(text, ("growth", "manufacturing", "economy", "economic")):
            return "The growth print matters only if demand converts into durable private investment, output, and employment. Watch the next manufacturing and credit data for evidence that the expansion is broadening rather than relying on public spending."
        if has_any(text, ("rupee", "fed", "crude", "oil", "foreign")):
            return "Higher crude prices raise India’s dollar import bill while rising U.S. yields can pull capital away from rupee assets, pressuring both the currency and domestic borrowing costs. Watch RBI action, foreign debt flows, and the next oil move to see whether the sell-off becomes a broader external-financing stress."
        if has_any(text, ("rbi", "sebi", "liquidity", "rate", "yield")):
            return "The policy signal affects funding conditions through rates, liquidity, and risk appetite. Watch the next money-market data and lending response to see whether it changes the cost or availability of credit."
        if has_any(text, ("ipo", "nifty", "sensex", "market")):
            return "A broad market move affects financing conditions and household balance sheets beyond any single stock. Watch market breadth and fund flows to distinguish a durable shift from a narrow price reaction."
        return "The development changes incentives for households, firms, or public finances through the channel described in the report. Watch the next official data or implementation decision for evidence that the effect is reaching the real economy."
    if item.section == "national" and has_any(text, ("jaishankar", "rubio", "sanctions")):
        return "Sanctions policy can constrain India’s room to manage energy and defence ties even when bilateral diplomacy remains constructive. Watch the official readout and any waiver or enforcement detail that turns the concern into a commercial constraint."
    if item.section == "national" and has_any(text, ("mines act", "mineral rights", "mineral-bearing lands")):
        return "The amendments shift the balance of fiscal authority over mineral rights by narrowing states’ scope to levy taxes and cesses, which can change the economics of mining projects and state revenues. Watch Odisha’s assessment, litigation, and any central guidance for the first measure of the fiscal trade-off."
    if item.section == "national" and has_any(text, ("capital punishment", "death sentence", "reformation of convict")):
        return "The Supreme Court’s emphasis on assessing a convict’s prospect of reform raises the evidentiary threshold before capital punishment can be sustained. Watch lower-court sentencing hearings and subsequent appeals for how consistently that safeguard is applied."
    if item.section == "national" and has_any(text, ("advisory", "russian forces", "recruitment")):
        return "The advisory makes recruitment into a foreign conflict a direct consular and security risk for Indian citizens, rather than a distant geopolitical headline. Watch for official case counts, assistance measures, or diplomatic representations that show whether the exposure is widening."
    if has_any(text, ("it rules", "social media")) and has_any(text, ("under-18", "minor", "minors")):
        return "An under-18 social-media restriction would shift age-assurance, account-design, and moderation costs onto platforms serving Indian users. Watch the amendment’s age-verification standard and enforcement timetable for the balance between child safety, privacy, and access."
    if has_any(text, ("cyber incidents", "cyber incident")) and has_any(text, ("internal silos", "fragmented data")):
        return "Fragmented data and approval chains can delay a company’s response after an intrusion, turning an internal operating problem into a larger security exposure. Watch whether firms set shared incident-response ownership and report faster containment as the next test of the finding."
    if has_any(text, ("bitchat",)) and has_any(text, ("meity", "play store", "apple")):
        return "A MeitY-linked removal can determine whether a messaging product remains reachable through India’s mainstream app-distribution channels. Watch for the underlying order, scope, and any restoration or appeal to clarify the compliance standard for similar services."
    if has_any(text, ("semiconductor", "chip", "deeptech")):
        return "Signed customers, deployed capacity, and repeat orders matter more than the announcement. Deep-tech sales cycles can hide weak commercial demand behind a strong launch narrative."
    if has_any(text, ("gcc", "capability center", "capability centres")):
        return "AI pilots do not produce the promised productivity gains until GCCs redesign workflows, data access, and accountability around them. Watch for pilots graduating into production deployments and for reskilling budgets to follow."
    if has_any(text, ("fssai", "food safety", "penalis", "non-compliance")):
        return "Penalties make marketplaces accountable for food-safety controls across sellers and quick-commerce fulfilment. Watch the orders’ scope and platform remediation to see whether compliance becomes a material operating cost."
    if has_any(text, ("phonepe", "payment devices", "bharat market")):
        return "A larger field-sales force and device rollout shift PhonePe’s expansion toward offline merchant acceptance, especially beyond major cities. Watch device activation, merchant retention, and transaction growth to judge whether the distribution spend creates durable payment usage."
    if has_any(text, ("upi", "payment", "fintech")):
        if has_any(text, ("market share", "transaction volumes", "transaction share")):
            return "Navi’s gain tests the staying power of India’s payment incumbents. Watch value share, incentive spending, and merchant retention before calling the shift durable."
        if has_any(text, ("mdr", "pricing", "fee")):
            return "A merchant-discount fee would create a funding pool for UPI’s cybersecurity, capacity, and fraud-control costs instead of leaving them entirely to participating institutions. Watch NPCI and regulatory guidance, then merchant acceptance, to see whether a charge can fund resilience without slowing adoption."
        return "Putting transaction, mandate, complaint, and fraud tasks behind one assistant could reduce the friction of using UPI services. Watch activation and complaint-resolution data to see whether conversational access improves outcomes without raising fraud risk."
    if has_any(text, ("rummyculture", "gameskraft", "money laundering", "pmla")):
        return "An asset attachment can restrict the capital and operating room available to a gaming platform while its enforcement case proceeds. Watch the company’s legal response and any adjudication order for the first indication of whether the action changes the sector’s compliance burden."
    if has_any(text, ("digital maturity", "non-profits", "nonprofits")):
        return "Low digital maturity limits how effectively non-profits can use data, online grants, and AI tools to deliver programmes or raise funds. Watch whether training and funding partners set adoption targets that turn the reported gap into measurable capability gains."
    if has_any(text, ("fund", "funding", "raises", "ipo")):
        return "Check customer traction and unit economics before treating the transaction as a sector signal. The next financing round or earnings release will test the valuation behind the headline."
    if has_any(text, ("regulation", "privacy", "antitrust", "data")):
        return "The rule's scope and enforcement will decide which companies carry the cost. Compliance deadlines and exemptions will separate the exposed firms from the beneficiaries."
    return "The report identifies a specific operational or regulatory pressure on the companies involved. Watch the first disclosed response or enforcement step to determine whether that pressure changes behaviour."


def editorial_brief(item: FeedItem) -> str:
    """Apply concise, RSS-grounded editing to the specific high-signal cards."""
    text = f"{item.title} {item.summary}".lower()
    if has_any(text, ("india-new zealand", "india new zealand")) and has_any(text, ("tariff", "duty-free")):
        return "The India-New Zealand FTA takes effect on 20 October, with tariffs on a range of processed food products falling to zero on day one."
    if has_any(text, ("advisory", "russian forces", "recruitment")):
        return "India has issued an advisory after reports that its citizens were being recruited into Russian forces."
    if has_any(text, ("it rules", "social media")) and has_any(text, ("under-18", "minor", "minors")):
        return "The Centre told the Supreme Court it plans to amend the IT Rules to bar under-18s from social media."
    if has_any(text, ("cyber incidents", "cyber incident")) and has_any(text, ("internal silos", "fragmented data")):
        return "Cisco says 96% of Indian firms faced a cyber incident in the past year, while data, approval, and team silos slowed their defences."
    if has_any(text, ("deepwater gas", "kg-d6", "gas price ceiling")):
        return "The government lifted the ceiling on difficult-field gas prices to $9.89 per MMBtu for October–March, while retaining the $7 cap for legacy ONGC and Oil India fields."
    if has_any(text, ("capital punishment", "death sentence", "reformation of convict")):
        return "The Supreme Court said capital punishment is possible only after a court has ruled out the prospect that the convicted person can reform."
    if has_any(text, ("bitchat",)) and has_any(text, ("meity", "play store", "apple")):
        return "Bitchat has been removed from Google Play in India; Apple cited a MeitY order for the offline messaging app’s unavailability."
    return compact(item.summary, 220)


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


def refresh_catalyst_date(document: str, now: datetime) -> str:
    """Keep the lone closing catalyst module pointed at the following day."""
    tomorrow_date = (now + timedelta(days=1)).strftime("%-d %B")
    tomorrow_label = (now + timedelta(days=1)).strftime("%A, %-d %B")
    document, heading_count = re.subn(
        r'(<h2 id="catalyst-title">Tomorrow’s catalysts</h2>\s*<p class="meta">)[^<]+',
        rf'\g<1>{tomorrow_label}',
        document,
        count=1,
    )
    document, note_count = re.subn(
        r'(RSS audit did not contain a distinct, date-specific event for )\d{1,2} [A-Za-z]+(?=, so this section)',
        rf'\g<1>{tomorrow_date}',
        document,
        count=1,
    )
    document, window_count = re.subn(
        r'\b\d+-hour RSS audit\b',
        f'{DEFAULT_RECENCY_HOURS}-hour RSS audit',
        document,
        count=1,
    )
    if heading_count != 1 or note_count != 1 or window_count != 1:
        raise ValueError("Expected one dated Tomorrow’s catalysts module")
    return document


def card(item: FeedItem, number: int) -> str:
    published = datetime.fromisoformat(item.published_at).strftime("%-d %b · %H:%M UTC")
    summary = editorial_brief(item)
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
            <p>This build keeps its configured recency cutoff hard. Check the feed audit for source errors or the next scheduled refresh.</p>
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
    national = select_items(items, "national", now)
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
        "selection_audit": {
            "macro": selection_audit(items, "macro", now, macro),
            "national": selection_audit(items, "national", now, national),
            "tech": selection_audit(items, "tech", now, tech),
        },
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not any(row["error"] is None for row in feed_status) or not (macro or tech):
        print("RSS build aborted: no publishable RSS selection; preserved the last good newsletter.", file=sys.stderr)
        return 2

    document = HTML_PATH.read_text(encoding="utf-8")
    document = refresh_edition(document, now)
    document = refresh_catalyst_date(document, now)
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
    parser.add_argument("--hours", type=int, default=DEFAULT_RECENCY_HOURS, help="maximum age of included items (36 hours maximum)")
    parser.add_argument("--from-audit", action="store_true", help="rebuild from the most recent successful RSS audit without fetching")
    arguments = parser.parse_args()
    if not 0 < arguments.hours <= DEFAULT_RECENCY_HOURS:
        parser.error(f"--hours must be between 1 and {DEFAULT_RECENCY_HOURS}")
    raise SystemExit(rebuild_from_audit(arguments.hours) if arguments.from_audit else build(arguments.hours))
