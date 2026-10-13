#!/usr/bin/env python3
"""Capture RSS evidence into a new run. Never select, render or edit the site."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from feeds import FEEDS, USER_AGENT, parse_payload
from newsletter import ROOT, TEMPLATE, candidate_id, digest, now_utc, publication_history, read, save_new, stamp


def retrieve(spec, raw_dir, attempts=3):
    source, lane, url = spec
    row = {'source': source, 'section': lane, 'url': url, 'error': None, 'attempts': []}
    for attempt in range(attempts):
        try:
            req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
            with urlopen(req, timeout=15) as response:
                payload = response.read(8 * 1024 * 1024 + 1)
            if len(payload) > 8 * 1024 * 1024:
                raise ValueError('Feed exceeds 8MB limit')
            name = digest(url.encode())[:16] + '-' + str(attempt + 1) + '.xml'
            raw_path = raw_dir / name
            with raw_path.open('xb') as stream:
                stream.write(payload)
            row.update(raw_path='raw/' + name, raw_sha256=digest(payload))
            items, drops = parse_payload(source, lane, payload)
            row['attempts'].append({'attempt': attempt + 1, 'at': now_utc().isoformat(), 'error': None})
            row.update(items_parsed=len(items), parser_drops=drops)
            return [asdict(x) for x in items], row
        except Exception as exc:
            row['attempts'].append({'attempt': attempt + 1, 'at': now_utc().isoformat(), 'error': f'{type(exc).__name__}: {exc}'})
            if isinstance(exc, ValueError):
                break
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2 ** attempt))
    row.update(error=row['attempts'][-1]['error'], items_parsed=0)
    return [], row


def capture(hours=36, *, replay=None, runs=None):
    if not 0 < hours <= 36:
        raise ValueError('--hours must be between 1 and 36')
    runs = Path(runs or ROOT / 'work/runs')
    now = now_utc()
    run_id = now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    run = runs / run_id
    run.mkdir(parents=True, exist_ok=False)
    with (run / 'template.html').open('xb') as stream:
        stream.write(TEMPLATE.read_bytes())
    if replay:
        old = read(replay)
        now = stamp(old['fetched_at'] if 'fetched_at' in old else old['generated_at'])
        all_items = old['items'] if 'items' in old else old['items_retained']
        feeds = old['feeds']
        mode = 'replay'
        save_new(run / 'replay-source.json', old)
    else:
        (run / 'raw').mkdir()
        with ThreadPoolExecutor(max_workers=5) as pool:
            fetched = list(pool.map(lambda spec: retrieve(spec, run / 'raw'), FEEDS))
        all_items = [x for items, _ in fetched for x in items]
        feeds = [status for _, status in fetched]
        mode = 'live'
        now = now_utc()
    cutoff = now - timedelta(hours=hours)
    candidates, seen = [], set()
    counts = {f['source']: {'fresh': 0, 'old': 0, 'future': 0, 'exact_duplicate': 0} for f in feeds}
    for source in all_items:
        row = {key: source[key] for key in ('source', 'section', 'title', 'summary', 'link', 'published_at')}
        date = stamp(row['published_at'])
        count = counts[row['source']]
        if date > now:
            count['future'] += 1
        elif date < cutoff:
            count['old'] += 1
        else:
            row['id'] = candidate_id(row)
            if row['id'] in seen:
                count['exact_duplicate'] += 1
                continue
            seen.add(row['id'])
            candidates.append(row)
            count['fresh'] += 1
    for feed in feeds:
        feed['window_counts'] = counts[feed['source']]
    save_new(run / 'capture.json', {'schema_version': 2, 'run_id': run_id, 'mode': mode,
        'captured_at': now.isoformat(), 'cutoff': cutoff.isoformat(), 'hours': hours,
        'feeds': feeds, 'candidates': sorted(candidates, key=lambda x: (x['published_at'], x['id']), reverse=True)})
    save_new(run / 'history.json', publication_history())
    print(f'RUN={run}')
    print(f'Captured {len(candidates)} candidates. Editorial review REQUIRED; no selection or confidence was generated.')
    if not candidates:
        print('HOLD: no fresh evidence. Capture and feed diagnostics retained.', file=sys.stderr)
    return run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hours', type=int, default=36)
    parser.add_argument('--replay', type=Path, help='Diagnostic-only replay; cannot be promoted')
    args = parser.parse_args()
    try:
        result = capture(args.hours, replay=args.replay)
        if not read(result / 'capture.json')['candidates']:
            raise SystemExit(2)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'Capture failed: {exc}\n')
