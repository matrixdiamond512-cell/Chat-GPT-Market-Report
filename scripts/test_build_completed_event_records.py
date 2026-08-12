from build_completed_event_records import compatible, make_record, surprise
from datetime import datetime
from zoneinfo import ZoneInfo


def main() -> None:
    assert surprise("3.0%", "2.8%") == ("+0.2pt", 0.20000000000000018)
    assert compatible("332.81", "3.4%") is False
    event = {"id":"x","status":"released","importance":3,"datetimeJst":"2026-08-12T21:30:00+09:00","country":"米国","title":"CPI前年比","category":"inflation","previous":"2.7%","forecast":"2.8%","actual":"3.0%"}
    row = make_record(event, datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Tokyo")))
    assert row and row["result_judgement"] == "上振れ（インフレ強）"
    assert row["initial_market_reaction"] == "反応確認困難"
    bad = dict(event, actual="332.81")
    assert make_record(bad, datetime.now(ZoneInfo("Asia/Tokyo")))["actual"] == "取得不能"
    missing = dict(event, actual="")
    assert make_record(missing, datetime.now(ZoneInfo("Asia/Tokyo"))) is None
    print("Completed event record tests passed")


if __name__ == "__main__":
    main()
