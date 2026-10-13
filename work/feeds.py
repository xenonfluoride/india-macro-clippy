#!/usr/bin/env python3
"""RSS source roster and normalization helpers; no editorial selection."""

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


USER_AGENT = "IndiaMacroClippy/1.0 RSS reader (personal newsletter)"
DEFAULT_RECENCY_HOURS = 36

FEEDS = (
    ("Business Standard Economy & Policy", "macro", "https://www.business-standard.com/rss/economy-policy-102.rss"),
    ("Business Standard Companies", "macro", "https://www.business-standard.com/rss/companies-101.rss"),
    ("Economic Times Economy", "macro", "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("The Hindu Economy", "macro", "https://www.thehindu.com/business/Economy/feeder/default.rss"),
    ("Mint Markets", "macro", "https://www.livemint.com/rss/markets"),
    ("Mint Companies", "macro", "https://www.livemint.com/rss/companies"),
    ("Mongabay India", "macro", "https://india.mongabay.com/feed/?post_type=post&feedtype=bulletpoints"),
    ("Hindustan Times India", "national", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"),
    ("NDTV India", "national", "https://feeds.feedburner.com/ndtvnews-india-news"),
    ("BBC News India", "national", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
    ("Economic Times Tech", "tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"),
    ("The Hindu Technology", "tech", "https://www.thehindu.com/sci-tech/technology/feeder/default.rss"),
    ("Mint Technology", "tech", "https://www.livemint.com/rss/technology"),
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


def parse_payload(source: str, section: str, payload: bytes):
    root = ET.fromstring(payload)
    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    items: list[FeedItem] = []
    drops = {"missing_title_or_link": 0, "missing_timestamp": 0, "updated_only": 0}
    for entry in entries:
        title = plain_text(child_text(entry, "title"))
        link = item_link(entry)
        published = child_text(entry, "pubdate", "published", "date")
        if not published and child_text(entry, "updated"):
            drops['updated_only'] += 1
        timestamp = parse_timestamp(published)
        summary = plain_text(child_text(entry, "description", "summary", "content", "encoded"))
        if not title or not link:
            drops['missing_title_or_link'] += 1
            continue
        if timestamp is None:
            drops['missing_timestamp'] += 1
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
    return items, drops
