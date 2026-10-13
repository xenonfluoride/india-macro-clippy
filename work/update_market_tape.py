#!/usr/bin/env python3
"""Capture separate, per-instrument Yahoo price snapshots; never edit HTML."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen
from newsletter import SYMBOLS, digest, now_utc, read, save_new, validate_market


def parse_quote(symbol, payload):
    result = payload['chart']['result'][0]
    values = result['indicators']['quote'][0]['close']
    points = [(ts, value) for ts, value in zip(result['timestamp'], values) if value is not None]
    if len(points) < 2:
        raise ValueError(f'Insufficient daily observations for {symbol}')
    prior, current = points[-2], points[-1]
    stamp = lambda ts: datetime.fromtimestamp(ts, timezone.utc).isoformat()
    return {'symbol': symbol, 'current': current[1], 'previous': prior[1],
        'observed_at': stamp(current[0]), 'previous_at': stamp(prior[0]),
        'change_pct': (current[1] / prior[1] - 1) * 100,
        'currency': result['meta'].get('currency'), 'kind': 'daily-bar-snapshot'}


def fetch(symbol):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe="")}?range=10d&interval=1d'
    errors = []
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent': 'IndiaMacroClippy/2.0'})
            with urlopen(req, timeout=15) as stream:
                payload = json.load(stream)
            return {'quote': parse_quote(symbol, payload), 'payload': payload, 'url': url, 'errors': errors}
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
            if attempt < 2:
                time.sleep(0.5 * 2 ** attempt)
    return {'error': errors[-1], 'errors': errors, 'url': url}


def update(run):
    run = Path(run)
    capture = read(run / 'capture.json')
    if (run / 'market.json').exists():
        raise ValueError('Price snapshot already exists; start a new run instead of overwriting evidence')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(SYMBOLS, pool.map(fetch, [x[0] for x in SYMBOLS.values()])))
    fetched = now_utc()
    (run / 'raw').mkdir(exist_ok=True)
    raw_path = run / 'raw' / ('market-fetch-' + fetched.strftime('%H%M%S%f') + '.json')
    save_new(raw_path, {'fetched_at': fetched.isoformat(), 'results': results})
    if any('error' in r for r in results.values()):
        raise ValueError('Market data incomplete after retries; diagnostics retained, publishing prohibited')
    market = {'schema_version': 2, 'run_id': capture['run_id'], 'provider': 'Yahoo Finance',
        'fetched_at': fetched.isoformat(), 'quotes': {name: row['quote'] for name, row in results.items()},
        'raw_path': str(raw_path.relative_to(run)), 'raw_sha256': digest(raw_path.read_bytes())}
    validate_market(market, fetched)
    save_new(run / 'market.json', market)
    print(f'Price snapshot saved: {run / "market.json"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    try:
        update(args.run)
    except (KeyError, TypeError, OSError, ValueError) as exc:
        parser.exit(1, f'Market Tape failed: {exc}\n')
