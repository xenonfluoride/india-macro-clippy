import importlib.util
import sys
import tempfile
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
    def test_roster_covers_independent_macro_and_tech_beats(self):
        sources = {source for source, _, _ in builder.FEEDS}
        self.assertTrue({
            "Business Standard Economy & Policy",
            "Economic Times Economy",
            "The Hindu Economy",
        }.issubset(sources))
        self.assertTrue({"Economic Times Tech", "The Hindu Technology"}.issubset(sources))
        self.assertTrue({"Hindustan Times India", "NDTV India", "BBC News India"}.issubset(sources))
        self.assertNotIn("The Hindu National", sources)
        self.assertFalse({
            "RBI", "SEBI", "MediaNama", "Mint Technology", "Indian Express Technology",
            "Indian Express Economy", "Indian Express Markets",
        } & sources)

    def test_recency_window_defaults_to_and_caps_at_36_hours(self):
        self.assertEqual(builder.DEFAULT_RECENCY_HOURS, 36)

    def test_national_feeds_keep_only_policy_and_strategy_stories(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        foreign_policy = item(
            "The Hindu National", "national", "India joins multilateral grouping at the UN",
            "India's foreign policy position is under discussion.",
        )
        local_crime = item(
            "The Hindu National", "national", "Hit-and-run incident reported in Delhi",
            "A local India crime report.",
        )
        state_spokesperson = item(
            "The Hindu National", "national", "State investment drive lifts FDI, says party spokesperson",
            "A state government spokesperson credits its investment drive.",
        )
        speculative_sector = item(
            "The Hindu National", "national", "Why rare-disease drugs could become India’s next pharma frontier",
            "An analysis of a possible industry opportunity.",
        )
        self.assertIsNotNone(builder.quality_score(foreign_policy, now))
        self.assertIsNone(builder.quality_score(local_crime, now))
        self.assertIsNone(builder.quality_score(state_spokesperson, now))
        self.assertIsNone(builder.quality_score(speculative_sector, now))

    def test_national_selection_allows_multiple_distinct_events_and_rewards_corroboration(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        court_ht = item("Hindustan Times India", "national", "FSSAI faces Supreme Court order", "India court directs FSSAI to review food safety rules")
        court_ndtv = item("NDTV India", "national", "Supreme Court asks FSSAI to review food safety", "India court issues FSSAI direction on food safety rules", 9)
        defence_bbc = item("BBC News India", "national", "India and France sign defence agreement", "India bilateral security agreement establishes defence cooperation", 8)
        selected = builder.select_items((court_ht, court_ndtv, defence_bbc), "national", now)
        self.assertEqual(len(selected), 2)
        self.assertIn(court_ht, selected)
        self.assertIn(defence_bbc, selected)
        self.assertGreater(
            builder.selection_score(court_ht, (court_ht, court_ndtv, defence_bbc), now),
            builder.quality_score(court_ht, now),
        )

    def test_tech_selection_keeps_one_card_per_repeated_event(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        mdr_court = item("YourStory", "tech", "UPI MDR: Court seeks responses", "India court reviews merchant discount rate", 10)
        mdr_protest = item("Inc42", "tech", "Retailers protest UPI MDR", "Indian retailers oppose merchant discount rate", 9)
        acquisition = item("Economic Times Tech", "tech", "HCLTech acquires an AI software firm", "India software company acquires automation business", 8)
        selected = builder.select_items((mdr_court, mdr_protest, acquisition), "tech", now)
        self.assertEqual(len(selected), 2)
        self.assertEqual(sum(builder.event_for(row) == "upi-mdr" for row in selected), 1)

    def test_render_includes_the_national_lane_in_the_audit_and_html(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        template = '''<span id="rss-status"></span>
<!-- RSS:MACRO:START --><!-- RSS:MACRO:END -->
<!-- RSS:NATIONAL:START --><!-- RSS:NATIONAL:END -->
<!-- RSS:TECH:START --><!-- RSS:TECH:END -->
<h2 id="catalyst-title">Tomorrow’s catalysts</h2><p class="meta">Wednesday, 17 September</p>
<p>The 36-hour RSS audit did not contain a distinct, date-specific event for 17 September, so this section does not recycle stories.</p>'''
        with tempfile.TemporaryDirectory() as directory:
            original_html, original_audit = builder.HTML_PATH, builder.AUDIT_PATH
            builder.HTML_PATH = Path(directory) / "newsletter.html"
            builder.AUDIT_PATH = Path(directory) / "newsletter.json"
            builder.HTML_PATH.write_text(template, encoding="utf-8")
            try:
                exit_code = builder.render_build(
                    [
                        item("Mint Markets", "macro", "India trade policy changes", "India trade policy update"),
                        item("The Hindu National", "national", "India joins multilateral forum", "India foreign policy update"),
                        item("Inc42", "tech", "PhonePe expands payment devices in Bharat", "India payment devices reach rural merchants"),
                    ],
                    [{"source": "test", "section": "macro", "url": "https://example.com", "items_parsed": 3, "error": None}],
                    now,
                    36,
                    "test",
                )
                audit = __import__("json").loads(builder.AUDIT_PATH.read_text(encoding="utf-8"))
                rendered = builder.HTML_PATH.read_text(encoding="utf-8")
            finally:
                builder.HTML_PATH, builder.AUDIT_PATH = original_html, original_audit
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(audit["selected"]["national"]), 1)
        self.assertEqual(audit["selection_audit"]["macro"][0]["decision"], "selected")
        self.assertIn("India joins multilateral forum", rendered)

    def test_rejects_routine_and_consumer_items(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        routine = item("RBI", "macro", "Result of the VRRR auction")
        omo = item("RBI", "macro", "Open Market Operation OMO sale")
        net_debt_sale = item("Business Standard Economy & Policy", "macro", "RBI completes net debt sale", "India liquidity operation")
        prediction = item("Mint Markets", "macro", "Stock Market prediction tomorrow")
        outlook = item("Mint Markets", "macro", "Global rate hike cycle begins — Sensex, Nifty outlook")
        stock_tip = item("Mint Markets", "macro", "Top stocks to buy on Monday")
        blue_chip_tip = item("Mint Markets", "macro", "Four blue-chip stocks in India with expanding margins")
        company_move = item("Mint Markets", "macro", "Why Adani Total Gas lost 5% as stocks performed")
        market_cues = item("Mint Markets", "macro", "How Asian markets and GIFT Nifty will impact Sensex today")
        promo = item("Inc42", "tech", "Spacetech’s Next Big Test, Weekly Funding Rundown")
        registry = item("RBI", "macro", "NBFCs surrender their Certificate of Registration")
        omo_detail = item("RBI", "macro", "Detailed Result: OMO Sale Auction")
        underwriting = item("RBI", "macro", "Underwriting Auction for sale of Government Securities")
        draft_ipo = item("Business Standard Companies", "macro", "Manufacturer files draft IPO papers")
        forecast_recap = item("Business Standard Economy & Policy", "macro", "Ratings agencies raise India growth forecast")
        irrelevant = item("Indian Express Economy", "macro", "Agency wins global public relations award", "Industry recognition announcement")
        review = item("Indian Express Technology", "tech", "Oppo Find X9 Ultra review", "India smartphone review")
        fundraising = item("Inc42", "tech", "India AI startup raises Series B funding", "Bengaluru startup funding announcement")
        executive_commentary = item("YourStory", "tech", "Google exec says engineering is a mindset", "India AI commentary")
        macro_executive_commentary = item("Mint Markets", "macro", "Fund MD & CEO says Dubai expansion is important", "India market commentary")
        forecast_roundup = item("Business Standard Economy & Policy", "macro", "India's consumer market to touch ₹3 trillion by 2030", "India market forecast")
        market_mover = item("Mint Markets", "macro", "India's AI enablers surge as data centre buildout gathers pace", "India technology shares rise")
        conditional_diplomacy = item("Business Standard Economy & Policy", "macro", "Minister may hold bilateral meeting with USTR this week", "India trade discussion could happen")
        investor_commentary = item("Mint Markets", "macro", "FIIs sell shares but five factors can bring them back — experts decode", "India investment commentary")
        ministerial_growth_commentary = item("The Hindu Economy", "macro", "Over 10% economic growth possible for India: Finance Minister", "India economy can grow faster")
        ministerial_discussion = item("Business Standard Economy & Policy", "macro", "Finance Minister discusses investment treaty with Qatar", "India trade and investment talks continue")
        index_recap = item("Mint Markets", "macro", "Nifty 50 down 13.5%, set for worst year in 15 years", "India market sentiment is weak")
        monthly_index_recap = item("Mint Markets", "macro", "Nifty 50 falls 6.3% in September, worst monthly series", "India market sentiment is weak")
        chairman_commentary = item("Business Standard Companies", "macro", "Hope RBI will find a common ground with us: Chairman", "India corporate discussion")
        currency_mover = item("Mint Markets", "macro", "Rupee hits two-month low: What does it mean for the Indian stock market?", "India foreign exchange market update")
        offshore_capex = item("Business Standard Companies", "macro", "India's company to invest in steel manufacturing in the US", "India company investment announcement")
        listing_mandate = item("Business Standard Companies", "macro", "Why Tata Sons faces a listing mandate", "India corporate governance update")
        fintech_outlook = item("YourStory", "tech", "Where is India's fintech story headed next?", "India payments and wealth outlook")
        fund_close = item("YourStory", "tech", "Venture firm marks first close of Fund III", "India fund will invest in startups")
        talent_report = item("YourStory", "tech", "India faces talent gap in GenAI and cloud skills", "India report measures workforce gap")
        stock_watchlist = item("Mint Markets", "macro", "Top stocks in focus today: shares that must be on radar", "India market watchlist")
        portfolio_tip = item("Mint Markets", "macro", "Greed and Fear index: investor portfolio has 22 stocks for the long term", "India market portfolio")
        technicals_tip = item("Mint Markets", "macro", "Expert View: stock selection crucial; three sectors have strong technicals", "India market expert commentary")
        ipo_tracker = item("Inc42", "tech", "Indian Startup IPO Tracker 2026", "India startup listing recap")
        global_ai_warning = item("The Hindu Technology", "tech", "Australia breach offers warning for countries like India", "India should bring regulations after an Australia breach")
        government_commentary = item("Economic Times Tech", "tech", "AI, semiconductors to drive India's next infrastructure push: FM Sitharaman", "India should invest in infrastructure")
        self.assertIsNone(builder.quality_score(routine, now))
        self.assertIsNone(builder.quality_score(omo, now))
        self.assertIsNone(builder.quality_score(net_debt_sale, now))
        self.assertIsNone(builder.quality_score(prediction, now))
        self.assertIsNone(builder.quality_score(outlook, now))
        self.assertIsNone(builder.quality_score(stock_tip, now))
        self.assertIsNone(builder.quality_score(blue_chip_tip, now))
        self.assertIsNone(builder.quality_score(company_move, now))
        self.assertIsNone(builder.quality_score(market_cues, now))
        self.assertIsNone(builder.quality_score(promo, now))
        self.assertIsNone(builder.quality_score(registry, now))
        self.assertIsNone(builder.quality_score(omo_detail, now))
        self.assertIsNone(builder.quality_score(underwriting, now))
        self.assertIsNone(builder.quality_score(draft_ipo, now))
        self.assertIsNone(builder.quality_score(forecast_recap, now))
        self.assertIsNone(builder.quality_score(irrelevant, now))
        self.assertIsNone(builder.quality_score(review, now))
        self.assertIsNone(builder.quality_score(fundraising, now))
        self.assertIsNone(builder.quality_score(executive_commentary, now))
        self.assertIsNone(builder.quality_score(macro_executive_commentary, now))
        self.assertIsNone(builder.quality_score(forecast_roundup, now))
        self.assertIsNone(builder.quality_score(market_mover, now))
        self.assertIsNone(builder.quality_score(conditional_diplomacy, now))
        self.assertIsNone(builder.quality_score(investor_commentary, now))
        self.assertIsNone(builder.quality_score(ministerial_growth_commentary, now))
        self.assertIsNone(builder.quality_score(ministerial_discussion, now))
        self.assertIsNone(builder.quality_score(index_recap, now))
        self.assertIsNone(builder.quality_score(monthly_index_recap, now))
        self.assertIsNone(builder.quality_score(chairman_commentary, now))
        self.assertIsNone(builder.quality_score(currency_mover, now))
        self.assertIsNone(builder.quality_score(offshore_capex, now))
        self.assertIsNone(builder.quality_score(listing_mandate, now))
        self.assertIsNone(builder.quality_score(fintech_outlook, now))
        self.assertIsNone(builder.quality_score(fund_close, now))
        self.assertIsNone(builder.quality_score(talent_report, now))
        self.assertIsNone(builder.quality_score(stock_watchlist, now))
        self.assertIsNone(builder.quality_score(portfolio_tip, now))
        self.assertIsNone(builder.quality_score(technicals_tip, now))
        self.assertIsNone(builder.quality_score(ipo_tracker, now))
        self.assertIsNone(builder.quality_score(global_ai_warning, now))
        self.assertIsNone(builder.quality_score(government_commentary, now))

    def test_selects_diverse_high_signal_items(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        candidates = [
            item("RBI", "macro", "Money Market Operations", "India liquidity data"),
            item("Bloomberg · Anup Roy", "macro", "India announces semiconductor logistics policy", "India manufacturing plan"),
            item("Mint Markets", "macro", "India refiners trim Russian crude purchases", "India oil buyers reassess cargoes"),
            item("Inc42", "tech", "PhonePe expands payment devices in Bharat", "India payment devices reach rural merchants"),
            item("MediaNama", "tech", "India reopens UPI pricing debate"),
            item("Indian Express Technology", "tech", "New AI model launches globally", "Global enterprise product launch"),
        ]
        macro = builder.select_items(candidates, "macro", now)
        tech = builder.select_items(candidates, "tech", now)
        self.assertEqual(set(row.source for row in macro), {"Bloomberg · Anup Roy", "Mint Markets"})
        self.assertEqual(set(row.source for row in tech), {"MediaNama", "Inc42"})

    def test_macro_themes_use_whole_words_and_cover_real_economy_stories(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        treaty = item("Economic Times Economy", "macro", "India keeps taxation out of investment treaty", "Foreign investors must use local remedies before arbitration")
        edf = item("Economic Times Economy", "macro", "India and EDF discuss EPR nuclear and pumped hydro", "Power ministry discusses deployment and regulation")
        drought = item("Business Standard Economy & Policy", "macro", "Maharashtra declares drought and crop-loan relief", "Rainfall deficit causes crop loss")
        water = item("Business Standard Economy & Policy", "macro", "AIIB plans water financing in India", "Water infrastructure will address rainfall deficit")
        logistics = item("Business Standard Companies", "macro", "Chip logistics facility planned in Gujarat", "India semiconductor workforce training is planned")
        self.assertFalse(builder.has_any("arbitration", ("rbi",)))
        self.assertIn("external-finance", builder.macro_topics(treaty))
        self.assertIn("energy-and-infrastructure", builder.macro_topics(edf))
        self.assertIn("food-and-rural", builder.macro_topics(drought))
        self.assertIn("climate-and-water", builder.macro_topics(water))
        self.assertIn("investment-and-industry", builder.macro_topics(logistics))
        for candidate in (treaty, edf, drought, water, logistics):
            self.assertIsNotNone(builder.quality_score(candidate, now))

    def test_macro_selection_avoids_repeating_the_same_theme(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        candidates = [
            item("Business Standard Economy & Policy", "macro", "India crude oil bill rises", "India crude import costs rise"),
            item("Mint Markets", "macro", "India refiners trim Russian oil cargoes", "India oil buyers reassess cargoes"),
            item("The Hindu Economy", "macro", "India trade agreement expands duty-free access", "India trade policy changes"),
        ]
        macro = builder.select_items(candidates, "macro", now)
        self.assertEqual(len(macro), 2)
        self.assertEqual({row.source for row in macro}, {"Business Standard Economy & Policy", "The Hindu Economy"})

    def test_macro_selection_leaves_a_slot_empty_for_a_thin_market_calendar(self):
        now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
        candidates = [
            item("Business Standard Economy & Policy", "macro", "India crude oil bill rises", "India crude import costs rise"),
            item("The Hindu Economy", "macro", "India trade agreement expands duty-free access", "India trade policy changes"),
            item("Mint Markets", "macro", "Stock market holidays next week", "India market calendar"),
        ]
        macro = builder.select_items(candidates, "macro", now)
        self.assertEqual(len(macro), 2)

    def test_strips_publisher_style_headline_tails(self):
        title = "Sensex rises after Fed decision — Experts explain the move"
        self.assertEqual(builder.display_title(title), "Sensex rises after Fed decision")
        self.assertEqual(builder.display_title("US Federal Reserve raises rates: Is RBI next?"), "US Federal Reserve raises rates")

    def test_payment_story_context_is_specific_to_the_event(self):
        share = item("Inc42", "tech", "Navi's UPI market share rises", "India transaction volumes rise")
        pricing = item("MediaNama", "tech", "UPI MDR pricing debate returns", "India payment fee policy")
        self.assertIn("value share", builder.why_it_matters(share))
        self.assertIn("cybersecurity", builder.why_it_matters(pricing))

    def test_digital_rupee_and_sanctions_notes_name_their_own_mechanisms(self):
        digital_rupee = item("Business Standard Companies", "macro", "Bank tests digital rupee rewards", "India CBDC wallet adds merchant payments")
        sanctions = item("The Hindu National", "national", "Jaishankar raises sanctions Act concerns", "India and U.S. officials discuss foreign policy")
        self.assertIn("merchant integration", builder.why_it_matters(digital_rupee))
        self.assertIn("waiver", builder.why_it_matters(sanctions))

    def test_refresh_edition_updates_date_and_increments_only_for_a_new_day(self):
        document = '<title>India Macro Clippy: 23 September 2026</title><p class="issue meta"><strong>Issue 003</strong><br />23 September 2026<br />'
        next_day = builder.refresh_edition(document, datetime(2026, 9, 24, 2, tzinfo=timezone.utc))
        same_day = builder.refresh_edition(next_day, datetime(2026, 9, 24, 3, tzinfo=timezone.utc))
        self.assertIn("Issue 004", next_day)
        self.assertIn("24 September 2026", next_day)
        self.assertIn("Issue 004", same_day)

    def test_refresh_catalyst_date_points_to_tomorrow(self):
        document = '''<h2 id="catalyst-title">Tomorrow’s catalysts</h2><p class="meta">Friday, 25 September</p>
        <p>The 36-hour RSS audit did not contain a distinct, date-specific event for 25 September, so this section does not recycle stories.</p>'''
        refreshed = builder.refresh_catalyst_date(document, datetime(2026, 9, 25, 2, tzinfo=timezone.utc))
        self.assertIn("Saturday, 26 September", refreshed)
        self.assertIn("event for 26 September", refreshed)

    def test_compact_keeps_complete_sentences(self):
        value = "First sentence is complete. Second sentence is deliberately much longer than the remaining room in this compact card."
        self.assertEqual(builder.compact(value, 30), "First sentence is complete.")
        self.assertEqual(builder.compact("The regulator took action against platforms…", 80), "The regulator took action against platforms.")


if __name__ == "__main__":
    unittest.main()
