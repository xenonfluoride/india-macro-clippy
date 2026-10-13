"""Regression suite for evidence contracts, isolation and publication."""
import copy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import newsletter as n
import build_newsletter as b
import update_market_tape as market
from feeds import FEEDS, parse_payload

NOW = datetime(2026, 10, 12, 8, tzinfo=timezone.utc)


def put(path, value):
    n.replace_file(path, n.encoded(value))


def approve_fixture(run):
    """TEST ONLY: synthetic check records are not editorial approval."""
    edition = n.read(run / 'edition.json')
    v = {'schema_version': 2, 'verdict': 'approved', 'reviewer': 'unit-test fixture ONLY',
         'checked_at': edition['created_at'], 'input_hashes': n.input_hashes(run),
         'template_sha256': n.digest(n.TEMPLATE.read_bytes()),
         'candidate_coverage': 'Test fixture accounts for every synthetic candidate in the input.',
         'hero': 'Test fixture hero names the synthetic selected policies without extra claims.',
         'catalysts': 'Test fixture contains no tomorrow-specific non-editorial event.',
         'cards': [{'id': c['id'], 'factual_support': 'Test fixture brief is an exact quotation from its evidence.',
                    'analysis': 'Test fixture mechanism and watch fields express distinct statements.',
                    'novelty': 'Test fixture events are distinct and not in the seeded history.'}
                   for c in edition['cards']]}
    put(run / 'verification.json', v)


def fixture(run, count=5):
    run.mkdir(parents=True, exist_ok=True)
    (run / 'raw').mkdir(exist_ok=True)
    source, _, url = FEEDS[0]
    candidates, decisions, cards = [], [], []
    root = ET.Element('rss')
    channel = ET.SubElement(root, 'channel')
    for i in range(count):
        row = {'source': source, 'section': 'macro', 'title': f'India approves policy number {i}',
               'summary': f'The Indian ministry approved policy number {i} for manufacturers.',
               'link': f'https://example.org/policy/{i}', 'published_at': (NOW - timedelta(hours=1)).isoformat()}
        row['id'] = n.candidate_id(row)
        candidates.append(row)
        entry = ET.SubElement(channel, 'item')
        for tag, value in [('title', row['title']), ('description', row['summary']), ('link', row['link']), ('pubDate', row['published_at'])]:
            ET.SubElement(entry, tag).text = value
        lane = n.LANES[i % 3]
        decisions.append({'id': row['id'], 'decision': 'select', 'confidence': 'high',
                          'event': row['summary'], 'actor': 'Indian ministry', 'action_type': 'policy approval',
                          'india_exposure': 'Domestic manufacturing policy', 'mechanism': 'Compliance duties for domestic producers',
                          'reason': 'A concrete policy action described in the source evidence.',
                          'materiality': 3, 'lane': lane, 'event_key': f'india-policy-number-{i}',
                          'evidence': [row['summary']]})
        cards.append({'id': row['id'], 'lane': lane, 'headline': row['title'], 'brief': row['summary'],
                      'mechanism': f'Policy number {i} could change compliance costs for domestic manufacturers.',
                      'watch': f'Watch the implementation notice for policy number {i} to establish when duties begin.',
                      'claims': [{'statement': row['summary'], 'evidence': [row['summary']]}]})
    raw = ET.tostring(root)
    (run / 'raw/rss.xml').write_bytes(raw)
    feeds = [{'source': s, 'section': lane, 'url': u, 'error': None if s == source else 'fixture unavailable'}
             for s, lane, u in FEEDS]
    feeds[0].update(raw_path='raw/rss.xml', raw_sha256=n.digest(raw))
    capture = {'schema_version': 2, 'run_id': 'fixture-v2', 'mode': 'live',
               'captured_at': NOW.isoformat(), 'cutoff': (NOW - timedelta(hours=36)).isoformat(),
               'hours': 36, 'feeds': feeds, 'candidates': candidates}
    put(run / 'capture.json', capture)
    put(run / 'history.json', {'schema_version': 2, 'entries': []})
    put(run / 'review.json', {'schema_version': 2, 'run_id': 'fixture-v2', 'editor': 'test fixture editor',
         'capture_sha256': n.digest((run / 'capture.json').read_bytes()), 'candidates': decisions})
    put(run / 'edition.json', {'schema_version': 2, 'run_id': 'fixture-v2', 'date': '2026-10-12',
         'created_at': NOW.isoformat(), 'issue': 11,
         'hero': 'Several Indian policy decisions set the domestic manufacturing agenda in this synthetic fixture.',
         'hero_card_ids': [c['id'] for c in cards], 'cards': cards, 'catalysts': [],
         'catalyst_review': 'The synthetic fixture contains no distinct date-specific signal for tomorrow.'})
    results, quotes = {}, {}
    for name, (symbol, currency) in n.SYMBOLS.items():
        payload = {'chart': {'result': [{'timestamp': [int((NOW - timedelta(days=d)).timestamp()) for d in (4, 3)],
                  'meta': {'currency': currency}, 'indicators': {'quote': [{'close': [100, 101]}]}}]}}
        results[name] = {'payload': payload}
        quotes[name] = market.parse_quote(symbol, payload)
    put(run / 'raw/market.json', {'results': results})
    put(run / 'market.json', {'schema_version': 2, 'run_id': 'fixture-v2', 'provider': 'Yahoo Finance',
         'fetched_at': NOW.isoformat(), 'quotes': quotes, 'raw_path': 'raw/market.json',
         'raw_sha256': n.digest((run / 'raw/market.json').read_bytes())})
    approve_fixture(run)
    data = n.validate(run, historical=True, check_html=False)
    (run / 'newsletter.html').write_text(n.render(data), encoding='utf-8')
    return run


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = fixture(Path(self.tmp.name) / 'run')

    def edit(self, name, mutate, reapprove=False):
        data = n.read(self.run / name)
        mutate(data)
        put(self.run / name, data)
        if reapprove:
            approve_fixture(self.run)

    def fail(self, match=None):
        with self.assertRaises((n.InvalidEdition, KeyError, ValueError, OSError)) as result:
            n.validate(self.run, now=NOW)
        if match:
            self.assertIn(match, str(result.exception))

    def test_valid_fixture(self):
        n.validate(self.run, now=NOW)

    def test_seven_card_issue_passes(self):
        run = fixture(Path(self.tmp.name) / 'seven', 7)
        n.validate(run, now=NOW)

    def test_old_placeholder_review_is_rejected(self):
        self.edit('review.json', lambda d: d['candidates'][0].update(actor='Not established beyond the RSS title and summary'), True)
        self.fail('Placeholder')

    def test_duplicate_requires_explicit_representative(self):
        self.edit('review.json', lambda d: d['candidates'][0].update(decision='duplicate', duplicate_of='missing-id'), True)
        self.fail('Duplicate must reference')

    def test_evidence_can_expire_during_editing(self):
        with self.assertRaises(n.InvalidEdition):
            n.validate(self.run, now=NOW + timedelta(hours=37))

    def test_original_roster_preserved(self):
        self.assertEqual(len(FEEDS), 15)
        self.assertTrue({'Mint Companies', 'Mint Technology', 'Mongabay India'} <= {x[0] for x in FEEDS})

    def test_missing_review_and_missing_verification_block(self):
        for name in ('review.json', 'verification.json'):
            original = (self.run / name).read_bytes()
            (self.run / name).unlink()
            self.fail()
            (self.run / name).write_bytes(original)

    def test_every_candidate_must_be_reviewed_once(self):
        self.edit('review.json', lambda d: d['candidates'].pop(), True)
        self.fail('Every candidate')

    def test_duplicate_review_cannot_hide_missing_candidate(self):
        self.edit('review.json', lambda d: d['candidates'].__setitem__(0, d['candidates'][1]), True)
        self.fail('Every candidate')

    def test_one_and_eight_card_issues_fail(self):
        for count in (1, 8):
            run = Path(self.tmp.name) / f'count-{count}'
            with self.assertRaisesRegex(n.InvalidEdition, 'five to seven'):
                fixture(run, count)

    def test_false_html_copy_fails(self):
        path = self.run / 'newsletter.html'
        path.write_text(path.read_text().replace('The Indian ministry approved policy number 0 for manufacturers.', 'India abolished all taxes overnight.'))
        self.fail('HTML differs')

    def test_false_edition_claim_fails_even_with_rebound_verification(self):
        self.edit('edition.json', lambda d: d['cards'][0].update(brief='India abolished all taxes overnight.'), True)
        self.fail('Claim must quote')

    def test_changed_copy_invalidates_semantic_approval(self):
        self.edit('edition.json', lambda d: d.update(hero='A different unsupported hero with enough characters to evade length checks.'))
        self.fail('Inputs changed')

    def test_source_records_cannot_be_deleted(self):
        self.edit('capture.json', lambda d: d['candidates'].pop(), True)
        self.fail('Candidate pool')

    def test_raw_feed_tampering_fails(self):
        (self.run / 'raw/rss.xml').write_text('<rss />')
        self.fail('RSS response changed')

    def test_future_timestamp_fails(self):
        self.edit('capture.json', lambda d: d['candidates'][0].update(published_at=(NOW + timedelta(days=30)).isoformat()), True)
        self.fail()

    def test_future_edition_fails(self):
        self.edit('edition.json', lambda d: d.update(created_at=(NOW + timedelta(days=1)).isoformat()), True)
        self.fail()

    def test_cutoff_cannot_be_extended(self):
        self.edit('capture.json', lambda d: d.update(cutoff=(NOW - timedelta(days=8)).isoformat()), True)
        self.fail('Cutoff')

    def test_wrong_visible_date_fails(self):
        path = self.run / 'newsletter.html'
        path.write_text(path.read_text().replace('12 October 2026', '1 January 2001'))
        self.fail('HTML differs')

    def test_wrong_json_date_fails(self):
        self.edit('edition.json', lambda d: d.update(date='2001-01-01'), True)
        self.fail('Wrong IST')

    def test_empty_prices_fail(self):
        self.edit('market.json', lambda d: d['quotes'].update({k: {} for k in n.SYMBOLS}), True)
        self.fail()

    def test_stale_symbol_fails(self):
        self.edit('market.json', lambda d: d['quotes']['Brent'].update(observed_at='2001-01-01T00:00:00+00:00'), True)
        self.fail()

    def test_price_must_match_raw_provider_record(self):
        self.edit('market.json', lambda d: d['quotes']['Brent'].update(current=100, change_pct=0), True)
        self.fail('Prices differ')

    def test_bad_currency_fails(self):
        self.edit('market.json', lambda d: d['quotes']['Brent'].update(currency='INR'), True)
        self.fail('currency')

    def test_nonfinite_prices_fail(self):
        self.edit('market.json', lambda d: d['quotes']['Brent'].update(current=float('nan')), True)
        self.fail('finite')

    def test_duplicate_event_fails(self):
        self.edit('review.json', lambda d: d['candidates'][1].update(event_key=d['candidates'][0]['event_key']), True)
        self.fail('Duplicate event')

    def test_prior_event_requires_real_update(self):
        c = n.read(self.run / 'capture.json')['candidates'][0]
        self.edit('history.json', lambda d: d['entries'].append({'event_key': 'india-policy-number-0', 'link': c['link']}), True)
        self.fail('Previously published')

    def test_proposals_do_not_receive_automatic_fact_substitutions(self):
        source = n.read(self.run / 'capture.json')
        self.assertFalse(hasattr(b, 'editorial_brief'))
        self.assertFalse(hasattr(b, 'quality_score'))
        self.assertNotIn('ElevenLabs', n.render(n.validate(self.run, now=NOW)))
        self.assertEqual(len(source['candidates']), 5)

    def test_sentences_are_separate(self):
        self.edit('edition.json', lambda d: d['cards'][0].update(watch=d['cards'][0]['mechanism']), True)
        self.fail('must differ')

    def test_three_sentences_fail(self):
        self.edit('edition.json', lambda d: d['cards'][0].update(watch='Watch the first implementation notice. Then watch compliance data.'), True)
        self.fail('exactly two')

    def test_hero_and_catalyst_coverage_required(self):
        self.edit('edition.json', lambda d: d.update(hero_card_ids=[]), True)
        self.fail('Hero')

    def test_publish_is_pointer_based_and_replay_prohibited(self):
        outputs = Path(self.tmp.name) / 'outputs'
        outputs.mkdir()
        with patch.object(n, 'now_utc', return_value=NOW):
            dest = n.promote(self.run, outputs, now=NOW)
        self.assertEqual(n.current_bundle(outputs), dest)
        n.check_accepted(outputs)
        self.assertTrue((dest / 'ledger.json').exists())
        before = (outputs / 'current.json').read_bytes()
        with self.assertRaises(n.InvalidEdition):
            n.promote(self.run, outputs, now=NOW)
        self.assertEqual(before, (outputs / 'current.json').read_bytes())

    def test_replay_cannot_be_promoted(self):
        self.edit('capture.json', lambda d: d.update(mode='replay'))
        self.edit('review.json', lambda d: d.update(capture_sha256=n.digest((self.run / 'capture.json').read_bytes())), True)
        with self.assertRaisesRegex(n.InvalidEdition, 'Replay'):
            n.promote(self.run, Path(self.tmp.name) / 'outputs', now=NOW)

    def test_failure_before_pointer_swap_preserves_site(self):
        outputs = Path(self.tmp.name) / 'outputs'
        outputs.mkdir()
        marker = outputs / 'india-macro-clippy.html'
        marker.write_text('last good site')
        real_replace = n.replace_file
        def failing_replace(path, payload):
            if Path(path).name == 'current.json':
                raise OSError('simulated disk failure')
            return real_replace(path, payload)
        with patch.object(n, 'replace_file', side_effect=failing_replace):
            with self.assertRaises(OSError):
                n.promote(self.run, outputs, now=NOW)
        self.assertEqual(marker.read_text(), 'last good site')
        self.assertFalse((outputs / 'current.json').exists())
        self.assertTrue((self.run / 'capture.json').exists())

    def test_pages_assembly_uses_only_accepted_bundle(self):
        import assemble_site
        outputs = Path(self.tmp.name) / 'outputs'
        outputs.mkdir()
        with self.assertRaises(n.InvalidEdition):
            assemble_site.assemble(Path(self.tmp.name) / 'missing-site', outputs)
        n.promote(self.run, outputs, now=NOW)
        site = assemble_site.assemble(Path(self.tmp.name) / 'site', outputs)
        self.assertEqual((site / 'index.html').read_bytes(), (self.run / 'newsletter.html').read_bytes())
        self.assertTrue((site / 'review.json').exists())

    def test_accepted_manifest_detects_tampering(self):
        outputs = Path(self.tmp.name) / 'outputs'
        outputs.mkdir()
        destination = n.promote(self.run, outputs, now=NOW)
        (destination / 'newsletter.html').write_text('unverified replacement')
        with self.assertRaisesRegex(n.InvalidEdition, 'Accepted bundle changed'):
            n.check_accepted(outputs)

    def test_parser_does_not_confuse_updated_with_publication(self):
        xml = b'<feed><entry><title>Story</title><link href="https://example.org"/><updated>2026-10-12T08:00:00Z</updated><summary>India news</summary></entry></feed>'
        rows, drops = parse_payload('test', 'macro', xml)
        self.assertEqual(rows, [])
        self.assertEqual(drops['updated_only'], 1)

    def test_capture_isolated_on_total_feed_failure(self):
        with patch.object(b, 'retrieve', side_effect=lambda spec, _: ([], {'source': spec[0], 'section': spec[1], 'url': spec[2], 'error': 'network failed'})):
            with patch.object(b, 'publication_history', return_value={'schema_version': 2, 'entries': []}):
                run = b.capture(runs=Path(self.tmp.name) / 'failed')
        self.assertEqual(n.read(run / 'capture.json')['candidates'], [])
        self.assertFalse((run / 'review.json').exists())
        self.assertFalse((run / 'newsletter.html').exists())

    def test_missing_market_observations_fail(self):
        payload = {'chart': {'result': [{'timestamp': [1], 'meta': {'currency': 'USD'}, 'indicators': {'quote': [{'close': [1]}]}}]}}
        with self.assertRaises(ValueError):
            market.parse_quote('BZ=F', payload)

    def test_all_market_failures_keep_diagnostics(self):
        (self.run / 'market.json').unlink()
        with patch.object(market, 'fetch', return_value={'error': 'network failed'}):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                market.update(self.run)
        self.assertFalse((self.run / 'market.json').exists())
        self.assertTrue(list((self.run / 'raw').glob('market-fetch-*.json')))


if __name__ == '__main__':
    unittest.main()
