"""Capture and reproduce the alternate daily Market Tape observations."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

PROVIDER = 'NSE, Upstox, ECB and BeCoin'
IST = ZoneInfo('Asia/Kolkata')
NSE_ARCHIVE = 'https://nsearchives.nseindia.com/content/indices/ind_close_all_{:%d%m%Y}.csv'
SOURCES = {
    'Nifty 50': ('NSE close', 'https://www.niftyindices.com/reports'),
    'Sensex': ('Upstox close', 'https://upstox.com/indices/sensex-share-price/'),
    'USD/INR': ('ECB reference cross', 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml'),
    'Brent': ('BeCoin futures', 'https://becoin.net/api/trading-asset-history?slug=brent'),
}


def download(url):
    request = Request(url, headers={'User-Agent': 'IndiaMacroClippy/2.0'})
    with urlopen(request, timeout=15) as response:
        return response.read().decode('utf-8-sig')


def capture_source(name, as_of):
    documents = []
    try:
        if name == 'Nifty 50':
            day = as_of.astimezone(IST).date()
            for offset in range(7):
                url = NSE_ARCHIVE.format(day - timedelta(days=offset))
                try:
                    documents.append({'url': url, 'body': download(url)})
                except HTTPError as error:
                    if error.code != 404:
                        raise
                    documents.append({'url': url, 'status': 404})
                if sum('body' in document for document in documents) == 2:
                    break
        else:
            url = SOURCES[name][1]
            documents.append({'url': url, 'body': download(url)})
        return {'documents': documents}
    except (OSError, ValueError) as error:
        return {'documents': documents, 'error': str(error)}


class SensexHistory(HTMLParser):
    """Extract rows of the dated Close table from Upstox's Sensex page."""

    def __init__(self):
        super().__init__()
        self.history = False
        self.row = None
        self.cell = None
        self.observations = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row == ['Day', 'Open', 'Close', 'Change %']:
                self.history = True
            elif self.history and len(self.row) == 4:
                day = datetime.strptime(self.row[0], '%d-%b-%y').date()
                close = float(self.row[2].replace('₹', '').replace(',', ''))
                self.observations.append((day, close))
            self.row = None
        elif tag == 'table':
            self.history = False


def observations(name, documents, fetched):
    if name == 'Nifty 50':
        points = []
        for offset, document in enumerate(documents):
            day = fetched.astimezone(IST).date() - timedelta(days=offset)
            if document['url'] != NSE_ARCHIVE.format(day):
                raise ValueError('Unexpected NSE archive date or URL')
            if document.get('status') == 404:
                continue
            rows = [row for row in csv.DictReader(io.StringIO(document['body']))
                    if row['Index Name'] == 'Nifty 50']
            if len(rows) != 1 or rows[0]['Index Date'] != day.strftime('%d-%m-%Y'):
                raise ValueError('NSE response does not identify the requested Nifty 50 session')
            points.append((day, float(rows[0]['Closing Index Value'])))
        return points, IST
    if len(documents) != 1 or documents[0]['url'] != SOURCES[name][1]:
        raise ValueError(f'Unexpected {name} source URL')
    body = documents[0]['body']
    if name == 'Sensex':
        parser = SensexHistory()
        parser.feed(body)
        return parser.observations, IST
    if name == 'USD/INR':
        points = []
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError as error:
            raise ValueError('Invalid ECB reference-rate XML') from error
        for element in root.iter():
            if 'time' in element.attrib:
                rates = {child.attrib['currency']: float(child.attrib['rate']) for child in element}
                points.append((date.fromisoformat(element.attrib['time']), rates['INR'] / rates['USD']))
        return points, ZoneInfo('Europe/Berlin')
    # BeCoin's most recent UTC daily bar can still be in progress.
    points = [(date.fromisoformat(row['Date']), float(row['Close']))
              for row in csv.DictReader(io.StringIO(body)) if row['Close']]
    return [(day, close) for day, close in points if day < fetched.date()], timezone.utc


def parse_quote(name, symbol, currency, result, fetched):
    if 'error' in result:
        raise ValueError(f'{name} source failed: {result["error"]}')
    points, zone = observations(name, result['documents'], fetched)
    if len(points) < 2 or len({day for day, _ in points}) != len(points):
        raise ValueError(f'Expected distinct dated observations for {name}')
    (prior_day, prior), (day, current) = sorted(points)[-2:]
    if prior <= 0 or current <= 0:
        raise ValueError(f'Expected positive prices for {name}')
    return {'symbol': symbol, 'currency': currency, 'current': current, 'previous': prior,
            'change_pct': (current / prior - 1) * 100, 'kind': 'daily-source-observation',
            'observed_at': datetime.combine(day, time(), zone).isoformat(),
            'previous_at': datetime.combine(prior_day, time(), zone).isoformat()}
