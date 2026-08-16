import unittest
from pathlib import Path


EVENTS_HTML = (Path(__file__).resolve().parents[1] / "events.html").read_text(
    encoding="utf-8"
)


class EventsResponsiveLayoutTests(unittest.TestCase):
    def test_completed_rows_have_mobile_card_hook(self):
        self.assertIn('<tr class="completed-event-row">', EVENTS_HTML)

    def test_mobile_completed_table_uses_cards(self):
        self.assertIn(
            "@media(max-width:700px){.completed-table-wrap{overflow:visible}",
            EVENTS_HTML,
        )
        self.assertIn(
            ".completed-table .completed-event-row{display:grid", EVENTS_HTML
        )
        self.assertIn(
            '.completed-table .completed-event-row>td:nth-child(10):before{display:block;content:"実測反応・過去傾向"',
            EVENTS_HTML,
        )

    def test_desktop_table_contract_is_preserved(self):
        self.assertIn(
            ".completed-table{width:100%;max-width:100%;min-width:0;table-layout:fixed}",
            EVENTS_HTML,
        )
        self.assertIn('<td colspan="11">', EVENTS_HTML)
        self.assertIn("${flagSvg(x.country)}", EVENTS_HTML)


if __name__ == "__main__":
    unittest.main()
