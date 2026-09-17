import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_newsletter.py")
SPEC = importlib.util.spec_from_file_location("newsletter_builder", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
sys.modules["newsletter_builder"] = builder
SPEC.loader.exec_module(builder)


def item(source, section, title, summary="India policy and markets", hour=10):
    return builder.FeedItem(
        source=source,
        section=section,
        title=title,
        link="https://example.com/story",
        published_at=datetime(2026, 9, 17, hour, tzinfo=timezone.utc).isoformat(),
        summary=summary,
    )


class QualityGateTests(unittest.TestCase):
    def test_rejects_routine_and_consumer_items(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        routine = item("RBI", "macro", "Result of the VRRR auction")
        irrelevant = item("Indian Express Economy", "macro", "Agency wins global public relations award", "Industry recognition announcement")
        review = item("Indian Express Technology", "tech", "Oppo Find X9 Ultra review", "India smartphone review")
        self.assertIsNone(builder.quality_score(routine, now))
        self.assertIsNone(builder.quality_score(irrelevant, now))
        self.assertIsNone(builder.quality_score(review, now))

    def test_selects_diverse_high_signal_items(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        candidates = [
            item("RBI", "macro", "Money Market Operations", "India liquidity data"),
            item("Bloomberg · Anup Roy", "macro", "India adviser calls for growth rethink"),
            item("Mint Markets", "macro", "Rupee reacts after Fed rate decision"),
            item("Inc42", "tech", "India AI chip startup raises new funding"),
            item("MediaNama", "tech", "India reopens UPI pricing debate"),
            item("Indian Express Technology", "tech", "New AI model launches globally", "Global enterprise product launch"),
        ]
        macro = builder.select_items(candidates, "macro", now)
        tech = builder.select_items(candidates, "tech", now)
        self.assertEqual(set(row.source for row in macro), {"Bloomberg · Anup Roy", "Mint Markets"})
        self.assertEqual(set(row.source for row in tech), {"MediaNama", "Inc42"})

    def test_strips_publisher_style_headline_tails(self):
        title = "Sensex rises after Fed decision — Experts explain the move"
        self.assertEqual(builder.display_title(title), "Sensex rises after Fed decision")

    def test_payment_story_context_is_specific_to_the_event(self):
        share = item("Inc42", "tech", "Navi's UPI market share rises", "India transaction volumes rise")
        pricing = item("MediaNama", "tech", "UPI MDR pricing debate returns", "India payment fee policy")
        self.assertIn("value share", builder.why_it_matters(share))
        self.assertIn("payment rails", builder.why_it_matters(pricing))


if __name__ == "__main__":
    unittest.main()
