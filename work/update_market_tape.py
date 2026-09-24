#!/usr/bin/env python3
"""Refresh the Market Tape from public Yahoo Finance chart data."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "outputs" / "india-macro-clippy.html"
AUDIT = ROOT / "outputs" / "india-macro-clippy-data.json"
USER_AGENT = "IndiaMacroClippy/1.0 market-data updater"
SPECS = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "USD/INR": "INR=X",
    "Brent": "BZ=F",
}


def fetch(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?range=10d&interval=1d"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=20) as response:
        result = json.load(response)["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    points = [(ts, close) for ts, close in zip(result["timestamp"], closes) if close is not None]
    if len(points) < 2:
        raise ValueError(f"Insufficient close data for {symbol}")
    previous = points[-2][1]
    current = points[-1][1]
    return {
        "symbol": symbol,
        "current": current,
        "previous": previous,
        "change_pct": (current / previous - 1) * 100,
        "points": points[-6:],
        "currency": result["meta"].get("currency", ""),
    }


def fmt(name: str, value: float) -> str:
    if name == "USD/INR":
        return f"₹{value:,.3f}"
    if name == "Brent":
        return f"${value:,.2f}"
    return f"{value:,.2f}"


def direction(name: str, change: float) -> tuple[str, str]:
    if name == "USD/INR":
        return ("down" if change > 0 else "up", "INR weaker" if change > 0 else "INR stronger")
    return ("up" if change > 0 else "down", f"{change:+.2f}%")


def tape(quotes: dict[str, dict], as_of: datetime) -> str:
    cards = []
    for name in ("Nifty 50", "Sensex", "USD/INR", "Brent"):
        quote_data = quotes[name]
        tone, label = direction(name, quote_data["change_pct"])
        cards.append(f'<div class="quote"><strong>{fmt(name, quote_data["current"])}</strong><span class="{tone}">{name} · {label}</span></div>')
    stamp = as_of.strftime("%-d %b close")
    cards_html = "\n        ".join(cards)
    return f'''<!-- MARKET:TAPE:START -->
      <div class="shell tape-grid">
        <p class="tape-label">Market tape<br /><span class="flat">Yahoo Finance price data · {stamp}</span></p>
        {cards_html}
      </div>
    <!-- MARKET:TAPE:END -->'''


def replace(document: str, name: str, content: str) -> str:
    pattern = rf"<!-- MARKET:{name}:START -->.*?<!-- MARKET:{name}:END -->"
    result, count = re.subn(pattern, content, document, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected one MARKET:{name} region, found {count}")
    return result


def main() -> None:
    quotes = {name: fetch(symbol) for name, symbol in SPECS.items()}
    as_of = datetime.fromtimestamp(quotes["Nifty 50"]["points"][-1][0], timezone.utc)
    document = PAGE.read_text(encoding="utf-8")
    document = replace(document, "TAPE", tape(quotes, as_of))
    PAGE.write_text(document, encoding="utf-8")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    audit["market_tape"] = {"as_of": as_of.isoformat(), "provider": "Yahoo Finance", "quotes": quotes}
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Market tape updated through {as_of.date()}")


if __name__ == "__main__":
    main()
