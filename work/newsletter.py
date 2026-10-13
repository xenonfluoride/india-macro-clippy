"""Evidence-first newsletter contracts, rendering and transactional promotion.

No function in this module chooses stories, writes editorial prose, or approves
semantic correctness. Those artifacts must be authored by the editor session.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / 'outputs'
TEMPLATE = ROOT / 'work/templates/newsletter.html'
IST = ZoneInfo('Asia/Kolkata')
LANES = ('macro', 'national', 'tech')
SYMBOLS = {'Nifty 50': ('^NSEI', 'INR'), 'Sensex': ('^BSESN', 'INR'),
           'USD/INR': ('INR=X', 'INR'), 'Brent': ('BZ=F', 'USD')}
INPUTS = ('capture.json', 'history.json', 'review.json', 'edition.json', 'market.json')


class InvalidEdition(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidEdition(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save_new(path, value):
    """Immutable artifact creation: never overwrite an earlier fetch or snapshot."""
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def replace_file(path, payload):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'Timestamp must include timezone')
    return dt.astimezone(timezone.utc)


def now_utc():
    return datetime.now(timezone.utc)


def candidate_id(row):
    fields = {k: row[k] for k in ('source', 'title', 'summary', 'link', 'published_at')}
    return digest(encoded(fields))[:24]


def safe_url(value):
    parsed = urlparse(value)
    return parsed.scheme in ('https', 'http') and bool(parsed.netloc)


def nonempty(value, minimum=8):
    return isinstance(value, str) and len(value.strip()) >= minimum


def sentence(value):
    """Conservative prose shape check; semantic completeness is separately reviewed."""
    if not nonempty(value, 25) or value.endswith(('...', '…')) or not value.endswith(('.', '?', '!')):
        return False
    scrubbed = re.sub(r'\b(?:U\.S\.|U\.K\.|Rs\.|Dr\.|Mr\.)', 'ABBR', value)
    return len(re.findall(r'[.!?](?:\s+|$)', scrubbed)) == 1


def current_bundle(outputs=OUTPUTS):
    pointer = Path(outputs) / 'current.json'
    if not pointer.exists():
        return None
    meta = read(pointer)
    name = meta['run_id']
    require(re.fullmatch(r'[A-Za-z0-9_-]+', name), 'Unsafe accepted run ID')
    target = Path(outputs) / 'editions' / name
    require(digest((target / 'manifest.json').read_bytes()) == meta['manifest_sha256'], 'Accepted manifest mismatch')
    return target


def publication_history(outputs=OUTPUTS):
    bundle = current_bundle(outputs)
    if bundle:
        return read(bundle / 'ledger.json')
    legacy = Path(outputs) / 'india-macro-clippy-data.json'
    entries = []
    if legacy.exists():
        old = read(legacy)
        for lane, rows in old.get('selected', {}).items():
            for row in rows:
                entries.append({'event_key': 'legacy-' + digest(row['link'].encode())[:16],
                    'link': row['link'], 'title': row['title'], 'summary': row['summary'],
                    'published_at': old['generated_at'], 'lane': lane})
    return {'schema_version': 2, 'entries': entries}


def input_hashes(run):
    return {name: digest((Path(run) / name).read_bytes()) for name in INPUTS}


def run_template(run):
    saved = Path(run) / 'template.html'
    return saved if saved.exists() else TEMPLATE


def validate_inputs(run, *, historical=False, now=None):
    """Fail closed. Returning data never means semantic truth was machine-proved."""
    run = Path(run)
    capture, history, review, edition, market = [read(run / f) for f in INPUTS]
    now = now or now_utc()
    require(all(d.get('schema_version') == 2 for d in (capture, history, review, edition, market)), 'Unsupported schema; legacy artifacts cannot be newly published')
    run_id = capture['run_id']
    require(re.fullmatch(r'[A-Za-z0-9_-]+', run_id), 'Unsafe run ID')
    require(all(d.get('run_id') == run_id for d in (review, edition, market)), 'Mixed run IDs')
    created = stamp(capture['captured_at'])
    edited = stamp(edition['created_at'])
    require(0 < capture['hours'] <= 36, 'Editorial window must be 1–36 hours')
    cutoff = created - timedelta(hours=capture['hours'])
    require(stamp(capture['cutoff']) == cutoff, 'Cutoff does not match capture window')
    require(created <= edited <= created + timedelta(hours=12), 'Edition must be completed within 12 hours of capture')
    require(edition['date'] == edited.astimezone(IST).date().isoformat(), 'Wrong IST edition date')
    if not historical:
        require(created <= now + timedelta(minutes=5), 'Capture is in the future')
        require(edited <= now + timedelta(minutes=5), 'Edition is in the future')
        require(now - created <= timedelta(hours=12), 'Capture is too old; fetch again')
        require(edition['date'] == now.astimezone(IST).date().isoformat(), 'Edition date is not today in IST')
    feeds = capture['feeds']
    require(bool(feeds) and any(not x['error'] for x in feeds), 'No successful source fetches')
    from feeds import FEEDS
    expected = {(name, url) for name, _, url in FEEDS}
    require({(x['source'], x['url']) for x in feeds} == expected, 'Feed roster incomplete or unrecognized')
    require(len(feeds) == len(expected), 'Duplicate feed status')
    recovered_ids = set()
    for feed in feeds:
        if feed.get('raw_path'):
            relative = Path(feed['raw_path'])
            require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe raw response path')
            require(digest((run / relative).read_bytes()) == feed['raw_sha256'], 'RSS response changed after capture')
            if capture['mode'] == 'live' and not feed['error']:
                from feeds import parse_payload
                from dataclasses import asdict
                parsed, _ = parse_payload(feed['source'], feed['section'], (run / relative).read_bytes())
                recovered_ids.update(candidate_id(asdict(x)) for x in parsed if cutoff <= stamp(x.published_at) <= created)
        elif capture['mode'] == 'live' and not feed['error']:
            raise InvalidEdition('Live capture missing raw source response')
    records = capture['candidates']
    ids = [x['id'] for x in records]
    require(bool(ids) and len(ids) == len(set(ids)), 'Empty or duplicate candidate IDs')
    if capture['mode'] == 'live':
        require(set(ids) == recovered_ids, 'Candidate pool differs from raw RSS; do not omit or edit records')
    else:
        require(capture['mode'] == 'replay', 'Unknown capture mode')
    sources = {f['source'] for f in feeds if not f['error']}
    for row in records:
        require(row['id'] == candidate_id(row), 'Candidate evidence was edited')
        require(row['source'] in sources and safe_url(row['link']), 'Invalid candidate provenance')
        require(cutoff <= stamp(row['published_at']) <= created, 'Candidate outside window or future-dated')
    by_id = {x['id']: x for x in records}
    require(review['capture_sha256'] == digest((run / 'capture.json').read_bytes()), 'Review is for different evidence')
    require(nonempty(review.get('editor'), 3), 'Reviewer identity missing')
    reviewed = review['candidates']
    require(len(reviewed) == len(ids) and {x['id'] for x in reviewed} == set(ids), 'Every candidate needs exactly one editorial review')
    decisions = {x['id']: x for x in reviewed}
    permitted = {'select', 'eligible', 'reject', 'duplicate', 'update'}
    for row in reviewed:
        require(row['decision'] in permitted, 'Invalid editorial decision')
        require(row['confidence'] in ('high', 'medium', 'low'), 'Invalid confidence')
        require(row['lane'] in LANES or row['lane'] == 'out-of-scope', 'Invalid editorial lane')
        for key in ('event', 'actor', 'action_type', 'india_exposure', 'mechanism', 'reason'):
            require(nonempty(row.get(key), 2 if key == 'actor' else 8), f'Incomplete {key} assessment for {row["id"]}')
            require(row[key] not in ('Not established beyond the RSS title and summary', 'Reviewed only for editorial suitability; no additional fact inferred.', 'See RSS title and summary'), 'Placeholder review is not editorial assessment')
        require(row.get('evidence') and all(isinstance(s, str) and s and s in (by_id[row['id']]['title'] + '\n' + by_id[row['id']]['summary']) for s in row['evidence']), 'Review evidence must quote the RSS text exactly')
        require(isinstance(row.get('materiality'), int) and 0 <= row['materiality'] <= 5, 'Materiality must be 0–5')
        if row['decision'] in ('select', 'update', 'duplicate'):
            require(nonempty(row.get('event_key')), 'Selected/duplicate event needs an explicit event key')
        if row['decision'] == 'duplicate':
            other = decisions.get(row.get('duplicate_of'))
            require(other is not None and other['id'] != row['id'] and other['decision'] != 'duplicate' and other.get('event_key') == row['event_key'], 'Duplicate must reference a reviewed representative of the same event')
    cards = edition['cards']
    require(5 <= len(cards) <= 7, 'Edition requires five to seven cards')
    card_ids = [c['id'] for c in cards]
    selected = {x['id'] for x in reviewed if x['decision'] in ('select', 'update')}
    require(len(set(card_ids)) == len(card_ids) and set(card_ids) == selected, 'Cards and selected decisions differ')
    event_keys, why_notes = set(), set()
    old_events = {x['event_key'] for x in history['entries']}
    old_links = {x['link'] for x in history['entries']}
    for card in cards:
        row, evidence = decisions[card['id']], by_id[card['id']]
        # Fetch age is not publication age: old candidates may expire during editing.
        reference_time = edited if historical else now
        require(reference_time - timedelta(hours=capture['hours']) <= stamp(evidence['published_at']) <= reference_time, 'Selected evidence expired before edition validation')
        require(row['confidence'] == 'high', 'Selected card needs high evidence confidence')
        require(row['lane'] in LANES and card['lane'] == row['lane'], 'Card lane differs from editorial review')
        require(row['event_key'] not in event_keys, 'Duplicate event occupies two cards')
        event_keys.add(row['event_key'])
        require(card['headline'] == evidence['title'], 'Preserve the RSS headline')
        require(nonempty(card['brief'], 35) and card['brief'].endswith(('.', '?', '!')) and not card['brief'].endswith(('...', '…')), 'Brief is incomplete')
        require(sentence(card['mechanism']) and sentence(card['watch']), 'Why it matters needs exactly two complete sentence fields')
        require(card['mechanism'] != card['watch'], 'Mechanism and next signal must differ')
        note = card['mechanism'] + ' ' + card['watch']
        require(note not in why_notes, 'Duplicate analysis')
        why_notes.add(note)
        if row['event_key'] in old_events or evidence['link'] in old_links or row.get('previous_event_key'):
            require(row['decision'] == 'update' and row.get('previous_event_key') in old_events and nonempty(row.get('new_evidence'), 35), 'Previously published event requires documented new evidence')
        claims = card['claims']
        require(bool(claims), 'Card needs explicit factual claim support')
        for claim in claims:
            require(nonempty(claim.get('statement')) and claim['statement'] in card['brief'], 'Claim must quote the composed brief')
            require(claim.get('evidence') and all(s and s in evidence['title'] + '\n' + evidence['summary'] for s in claim['evidence']), 'Factual claim lacks exact RSS support spans')
        # Every sentence of the brief must have a mapped claim, not just one token.
        require(' '.join(c['statement'] for c in claims) == card['brief'], 'Claims do not cover the entire brief')
    require(nonempty(edition.get('hero'), 50), 'Edition-specific hero missing')
    require(set(edition.get('hero_card_ids', [])) == set(card_ids), 'Hero must be reviewed against the final slate')
    require(isinstance(edition.get('issue'), int) and edition['issue'] > 0, 'Issue number missing')
    tomorrow = (edited.astimezone(IST) + timedelta(days=1)).date().isoformat()
    catalysts = edition.get('catalysts', [])
    require(len(catalysts) <= 3, 'Too many catalysts')
    require(nonempty(edition.get('catalyst_review'), 35), 'Record the dated-catalyst review, even when none qualify')
    for c in catalysts:
        require(c['id'] in by_id and c['id'] not in selected and c['date'] == tomorrow, 'Catalyst must be distinct and dated tomorrow')
        require(nonempty(c['text']) and c['evidence'] in by_id[c['id']]['title'] + '\n' + by_id[c['id']]['summary'], 'Catalyst lacks RSS evidence')
        require(edited - timedelta(hours=capture['hours']) <= stamp(by_id[c['id']]['published_at']), 'Catalyst evidence expired')
    validate_market(market, edited)
    price_path = Path(market['raw_path'])
    require(not price_path.is_absolute() and '..' not in price_path.parts, 'Unsafe market evidence path')
    raw_prices = run / price_path
    require(digest(raw_prices.read_bytes()) == market['raw_sha256'], 'Market response changed')
    from update_market_tape import parse_quote
    payload = read(raw_prices)
    for name, (symbol, _) in SYMBOLS.items():
        require(parse_quote(symbol, payload['results'][name]['payload']) == market['quotes'][name], 'Prices differ from captured provider response')
    return capture, history, review, edition, market


def validate_market(market, at):
    require(market.get('provider') == 'Yahoo Finance', 'Wrong price provider')
    fetched = stamp(market['fetched_at'])
    require(abs((at - fetched).total_seconds()) <= 12 * 3600, 'Price fetch must belong to this edition')
    require(set(market['quotes']) == set(SYMBOLS), 'Market Tape snapshot incomplete')
    for name, (symbol, currency) in SYMBOLS.items():
        q = market['quotes'][name]
        require(q['symbol'] == symbol and q['currency'] == currency, 'Wrong symbol or currency')
        for key in ('current', 'previous', 'change_pct'):
            require(isinstance(q[key], (int, float)) and not isinstance(q[key], bool) and math.isfinite(q[key]), 'Price must be a finite number')
        require(q['current'] > 0 and q['previous'] > 0, 'Prices must be positive')
        observed, previous = stamp(q['observed_at']), stamp(q['previous_at'])
        require(previous < observed <= fetched, 'Invalid per-symbol observation order')
        # Explicit bounded weekend tolerance. Longer holidays fail closed.
        require(fetched - observed <= timedelta(hours=96), 'Price observation is stale (96-hour maximum)')
        require(abs(q['change_pct'] - (q['current'] / q['previous'] - 1) * 100) < 1e-8, 'Price change does not match observations')


def validate_verification(run, data):
    run = Path(run)
    v = read(run / 'verification.json')
    require(v.get('schema_version') == 2 and v.get('verdict') == 'approved', 'Explicit semantic verification missing')
    require(nonempty(v.get('reviewer'), 3), 'Verification reviewer missing')
    require(v.get('input_hashes') == input_hashes(run), 'Inputs changed after semantic verification')
    require(v.get('template_sha256') == digest(run_template(run).read_bytes()), 'Renderer template changed after verification')
    edition = data[3]
    checks = v.get('cards', [])
    require(len(checks) == len(edition['cards']) and {c['id'] for c in checks} == {c['id'] for c in edition['cards']}, 'Semantic verification must cover every card')
    for card in checks:
        for key in ('factual_support', 'analysis', 'novelty'):
            require(nonempty(card.get(key), 35), f'Semantic check missing: {key}')
    for key in ('candidate_coverage', 'hero', 'catalysts'):
        require(nonempty(v.get(key), 35), f'Edition verification missing: {key}')
    require(stamp(v['checked_at']) >= stamp(edition['created_at']), 'Verification predates composition')
    require(stamp(v['checked_at']) <= stamp(edition['created_at']) + timedelta(hours=12), 'Verification too late for this edition')


def render(data, template_path=None):
    capture, _, review, edition, market = data
    records = {x['id']: x for x in capture['candidates']}
    escape = html.escape
    lanes = {lane: [] for lane in LANES}
    n = 0
    for lane in LANES:
        for card in [c for c in edition['cards'] if c['lane'] == lane]:
            n += 1
            source = records[card['id']]
            published = stamp(source['published_at']).strftime('%d %b · %H:%M UTC')
            lanes[lane].append(f'<article class="story" data-candidate="{card["id"]}"><div class="story-no">{n:02d}</div><div><h3>{escape(card["headline"])}</h3><p>{escape(card["brief"])}</p><p class="why"><span>Why it matters</span><br />{escape(card["mechanism"])} {escape(card["watch"])}</p><p class="source">RSS · <a href="{escape(source["link"], quote=True)}">{escape(source["source"])}, {published}</a></p></div></article>')
    market_cards = []
    for name in SYMBOLS:
        q = market['quotes'][name]
        value = (f'₹{q["current"]:,.3f}' if name == 'USD/INR' else f'${q["current"]:,.2f}' if name == 'Brent' else f'{q["current"]:,.2f}')
        change = q['change_pct']
        tone = 'flat' if change == 0 else 'up' if change > 0 else 'down'
        if name == 'USD/INR':
            tone = 'flat' if change == 0 else 'down' if change > 0 else 'up'
        label = stamp(q['observed_at']).strftime('%d %b %H:%M UTC')
        market_cards.append(f'<div class="quote"><strong>{value}</strong><span class="{tone}">{escape(name)} · {change:+.2f}%</span><span class="flat">{label}</span></div>')
    tape = '<div class="shell tape-grid"><p class="tape-label">Market tape<br /><span class="flat">Yahoo Finance price data · daily bar snapshots</span></p>' + ''.join(market_cards) + '</div>'
    tomorrow = (stamp(edition['created_at']).astimezone(IST) + timedelta(days=1)).strftime('%A, %-d %B')
    catalyst_body = '<p>No separate date-specific catalyst qualified in this RSS audit.</p>'
    if edition['catalysts']:
        catalyst_body = ''.join(f'<p>{escape(c["text"])} <a href="{escape(records[c["id"]]["link"], quote=True)}">{escape(records[c["id"]]["source"])}</a></p>' for c in edition['catalysts'])
    catalysts = f'<section class="catalyst-section" aria-labelledby="catalyst-title"><div class="section-head"><h2 id="catalyst-title">Tomorrow’s catalysts</h2><p class="meta">{tomorrow}</p></div><div class="catalysts">{catalyst_body}</div></section>'
    values = {'DATE': stamp(edition['created_at']).astimezone(IST).strftime('%-d %B %Y'), 'ISSUE': f'{edition["issue"]:03d}',
        'RUN_LABEL': escape('RSS edition · ' + capture['run_id']), 'HERO': escape(edition['hero']),
        'MARKET': tape, 'CATALYSTS': catalysts}
    values.update({lane.upper(): '\n'.join(lanes[lane]) or '<p>No qualifying story selected for this section.</p>' for lane in LANES})
    template = Path(template_path or TEMPLATE).read_text(encoding='utf-8')
    return re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: values[m[1]], template)


def validate(run, *, historical=False, now=None, check_html=True):
    data = validate_inputs(run, historical=historical, now=now)
    validate_verification(run, data)
    if check_html:
        require((Path(run) / 'newsletter.html').read_text(encoding='utf-8') == render(data, run_template(run)), 'HTML differs from verified edition; re-review inputs, never hand-edit HTML')
    return data


def compose(run, *, historical=False):
    data = validate(run, historical=historical, check_html=False)
    replace_file(Path(run) / 'newsletter.html', render(data, run_template(run)).encode())
    return validate(run, historical=historical)


def promote(run, outputs=OUTPUTS, *, now=None):
    run, outputs = Path(run), Path(outputs)
    data = validate(run, now=now)
    capture, history, review, edition, market = data
    require(capture['mode'] == 'live', 'Replay/shadow runs cannot be published')
    require(history == publication_history(outputs), 'Publication history changed; re-review novelty against latest edition')
    require(not (run / 'promotion.json').exists(), 'Run already promoted')
    editions = outputs / 'editions'
    editions.mkdir(parents=True, exist_ok=True)
    lock = outputs / '.promotion.lock'
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise InvalidEdition('Another promotion is active; inspect the lock before retrying')
    pending = None
    try:
        # Recheck under the lock; concurrent editors must not lose ledger entries.
        require(history == publication_history(outputs), 'Publication history changed during promotion')
        destination = editions / capture['run_id']
        require(not destination.exists(), 'Accepted edition already exists')
        pending = Path(tempfile.mkdtemp(prefix='.pending-', dir=editions))
        for name in INPUTS + ('verification.json', 'newsletter.html'):
            shutil.copyfile(run / name, pending / name)
        shutil.copyfile(run_template(run), pending / 'template.html')
        if (run / 'raw').exists():
            shutil.copytree(run / 'raw', pending / 'raw')
        by_id = {x['id']: x for x in capture['candidates']}
        decisions = {x['id']: x for x in review['candidates']}
        entries = list(history['entries'])
        for card in edition['cards']:
            row = by_id[card['id']]
            entries.append({'event_key': decisions[card['id']]['event_key'], 'link': row['link'],
                'title': row['title'], 'summary': row['summary'], 'published_at': edition['created_at'], 'lane': card['lane']})
        save_new(pending / 'ledger.json', {'schema_version': 2, 'entries': entries})
        files = {str(p.relative_to(pending)): digest(p.read_bytes()) for p in pending.rglob('*') if p.is_file()}
        save_new(pending / 'manifest.json', {'schema_version': 2, 'run_id': capture['run_id'], 'files': files})
        validate(pending, now=now)
        pending.rename(destination)
        pending = None
        pointer = {'schema_version': 2, 'run_id': capture['run_id'], 'manifest_sha256': digest((destination / 'manifest.json').read_bytes())}
        # The single pointer is the only authoritative publication change.
        replace_file(outputs / 'current.json', encoded(pointer))
        try:
            save_new(run / 'promotion.json', pointer)
        except OSError as error:
            # Promotion already committed. A convenience receipt must not turn
            # that success into an ambiguous failed transaction.
            print(f'WARN: edition accepted, but run receipt could not be saved: {error}', file=sys.stderr)
        return destination
    finally:
        os.close(lock_fd)
        lock.unlink()
        if pending is not None:
            shutil.rmtree(pending)


def check_accepted(outputs=OUTPUTS):
    bundle = current_bundle(outputs)
    require(bundle is not None, 'No v2 accepted edition; legacy site remains unchanged')
    manifest = read(bundle / 'manifest.json')
    actual = {str(p.relative_to(bundle)): digest(p.read_bytes()) for p in bundle.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    require(actual == manifest['files'], 'Accepted bundle changed')
    require(read(bundle / 'capture.json')['mode'] == 'live', 'Accepted edition must originate from a live capture')
    validate(bundle, historical=True)
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('context', 'verification-context', 'validate', 'render', 'promote', 'check-accepted'))
    parser.add_argument('--run', type=Path)
    parser.add_argument('--historical', action='store_true', help='Replay validation only; never accepted by promote')
    parser.add_argument('--offset', type=int, default=0, help='First candidate for context output')
    parser.add_argument('--limit', type=int, default=40, help='Context batch size, maximum 50')
    args = parser.parse_args()
    try:
        if args.command == 'check-accepted':
            print(check_accepted())
            return
        require(args.run is not None, '--run is required')
        if args.command == 'context':
            require(args.offset >= 0 and 1 <= args.limit <= 50, 'Invalid context batch bounds')
            c = read(args.run / 'capture.json')
            pool = c.pop('candidates')
            end = min(len(pool), args.offset + args.limit)
            print(json.dumps({'capture': c, 'total_candidates': len(pool), 'offset': args.offset,
                'next_offset': end if end < len(pool) else None,
                'candidates': pool[args.offset:end], 'history': read(args.run / 'history.json')}, ensure_ascii=False, indent=2))
        elif args.command == 'verification-context':
            validate_inputs(args.run, historical=args.historical)
            print(json.dumps({'input_hashes': input_hashes(args.run), 'template_sha256': digest(run_template(args.run).read_bytes()), 'note': 'Review every claim and analysis against capture; author verification.json yourself. This command does not approve anything.'}, indent=2))
        elif args.command == 'validate':
            validate(args.run, historical=args.historical)
            print('PASS: contracts, exact rendering and semantic-review binding verified')
        elif args.command == 'render':
            compose(args.run, historical=args.historical)
            print(args.run / 'newsletter.html')
        elif args.command == 'promote':
            require(not args.historical, 'Cannot promote with historical validation')
            print(promote(args.run))
    except (InvalidEdition, KeyError, TypeError, ValueError, OSError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
