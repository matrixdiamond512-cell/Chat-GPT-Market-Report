import unittest
from pathlib import Path

from scripts.reporting.timeline import TIMELINE_COLUMNS, TIMELINE_PERIODS, validate_timeline
from scripts.validate_market_reports import validate_report_content


def timeline_text(slot: str, omit: str | None = None, numeric_only: str | None = None) -> str:
    lines = [
        "1．概要",
        "本文",
        "2．市場時系列",
        "|" + "|".join(TIMELINE_COLUMNS) + "|",
        "|---|---|---|---|---|---|---|",
    ]
    for period, _aliases in TIMELINE_PERIODS[slot]:
        if period == omit:
            continue
        event = "市場の状態を確認し、売買材料の変化を整理した。"
        reaction = "日経先物と半導体株が売られ、為替は円高方向へ動いた。"
        meaning = "金利低下との連動を示し、次の市場の主導要因として残る。"
        if period == numeric_only:
            event = "日経225 -2.4%"
        lines.append(
            f"|{period}|09:00-10:00|{event}|{reaction}|{meaning}|"
            "市場観測時刻 09:30、根拠 F-001。|次の時間帯は金利と先物の反応を確認する。|"
        )
    lines += ["", "3．次の項目", "本文"]
    return "\n".join(lines)


class TimelineValidationTests(unittest.TestCase):
    def test_all_four_slots_accept_complete_periods(self):
        for slot in TIMELINE_PERIODS:
            with self.subTest(slot=slot):
                self.assertEqual([], validate_timeline(timeline_text(slot), slot))

    def test_all_four_slots_reject_a_missing_period(self):
        for slot, periods in TIMELINE_PERIODS.items():
            with self.subTest(slot=slot):
                errors = validate_timeline(timeline_text(slot, omit=periods[0][0]), slot)
                self.assertTrue(any("必須時間帯が不足" in error for error in errors))

    def test_numeric_price_row_is_not_a_timeline_entry(self):
        errors = validate_timeline(timeline_text("16:00", numeric_only="前場序盤"), "16:00")
        self.assertTrue(any("出来事・市場状態" in error for error in errors))

    def test_news_time_requires_separate_time_classification(self):
        text = timeline_text("12:00").replace(
            "市場観測時刻 09:30、根拠 F-001。", "時刻未確認、根拠 F-001。"
        ).replace("市場の状態を確認し、売買材料の変化を整理した。", "ニュース10:15に掲載され、市場が反応した。")
        errors = validate_timeline(text, "12:00")
        self.assertTrue(any("時刻区分が不明" in error for error in errors))

    def test_2100_rejects_future_event_but_allows_planned_release(self):
        text = timeline_text("21:00").replace(
            "市場の状態を確認し、売買材料の変化を整理した。",
            "発表時刻 22:30の指標結果が出て、市場が反応した。",
            1,
        )
        errors = validate_timeline(text, "21:00")
        self.assertTrue(any("21:00時点より後" in error for error in errors))

        planned = timeline_text("21:00").replace(
            "市場の状態を確認し、売買材料の変化を整理した。",
            "22:30発表予定の指標を控え、市場は結果を待っている。",
            1,
        )
        self.assertFalse(any("21:00時点より後" in error for error in validate_timeline(planned, "21:00")))

    def test_2100_unqualified_late_event_is_rejected_but_prior_day_allowed(self):
        baseline = timeline_text("21:00")
        source = "市場の状態を確認し、売買材料の変化を整理した。"
        asserted = baseline.replace(source, "22:30に指標が発表され、市場が反応した。", 1)
        self.assertTrue(any("21:00時点より後" in error
                            for error in validate_timeline(asserted, "21:00")))
        scheduled = baseline.replace(source, "22:30発表予定の指標を控え、市場は待っている。", 1)
        self.assertFalse(any("21:00時点より後" in error
                             for error in validate_timeline(scheduled, "21:00")))
        historical = baseline.replace(source, "前日22:30の指標が発表され、市場が反応した。", 1)
        self.assertFalse(any("21:00時点より後" in error
                             for error in validate_timeline(historical, "21:00")))

    def test_price_only_legacy_timeline_without_contract_fails(self):
        text = "1．市場の動き（日本時間・時系列）\n08:50 日経先物 68,090円\n11:30 日経平均 67,292円\n2．変化"
        self.assertTrue(validate_timeline(text, "16:00"))

    def test_existing_python_report_gate_checks_the_timeline(self):
        valid_errors, valid_warnings = [], []
        validate_report_content({"time": "16:00", "fullText": timeline_text("16:00")}, "fixture", True, valid_errors, valid_warnings)
        self.assertFalse(any("TIMELINE_CHECK" in error for error in valid_errors))

        invalid_errors, invalid_warnings = [], []
        validate_report_content(
            {"time": "16:00", "fullText": "1．市場時系列\n08:50 日経先物 68,090円\n2．変化"},
            "fixture", True, invalid_errors, invalid_warnings,
        )
        self.assertTrue(any("TIMELINE_CHECK" in error for error in invalid_errors))

    def test_20261013_original_price_list_fails_the_new_requirement(self):
        fixture = Path(__file__).parent / "fixtures" / "market_report_20261013_1600_original.txt"
        errors = validate_timeline(fixture.read_text(encoding="utf-8"), "16:00")
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
